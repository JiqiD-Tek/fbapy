# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : service.py
@Author  : OpenAI
@Date    : 2026/04/13
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid

from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from time import monotonic
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from backend.app.cloud.schema.resource.huoshan import (
    HuoshanRoleStoryRoleInfo,
    HuoshanRoleStoryScriptLine,
    HuoshanRoleStoryScriptParam,
    HuoshanRoleStoryScriptResult,
    HuoshanRoleStoryScriptTaskResult,
    HuoshanStoryGenerateParam,
    HuoshanStoryGenerateResult,
    HuoshanStoryBgmInfo,
    HuoshanStorySynthesisParam,
    HuoshanStorySynthesisResult,
    HuoshanVoiceListParam,
    HuoshanVoiceListResult,
    HuoshanVoiceStatus,
)
from backend.app.cloud.service.resource.role_service import cloud_role_service
from backend.app.cloud.service.resource.song_service import cloud_song_service
from backend.common.providers.ali_oss import oss_client
from backend.common.providers.doubao import DEFAULT_DOUBAO_STORY_MODEL, create_async_doubao_client, doubao_provider
from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.database.redis import redis_client
from backend.utils.timezone import timezone

from backend.app.cloud.service.resource.huoshan.config import (
    CLONE_VOICE_RESOURCE_ID_V2,
    VoiceProfile,
    get_public_voice,
    get_voice_name,
    get_voice_profile,
    get_voice_project_for_speaker,
)
from backend.app.cloud.service.resource.huoshan.audio_tools import mix_audio_with_bgm
from backend.app.cloud.service.resource.huoshan.client import HuoshanLongTextTTSClient, HuoshanOpenAPIClient
from backend.app.cloud.service.resource.huoshan.exceptions import HuoshanAPIError, HuoshanOpenAPIError, HuoshanTTSError
from backend.app.cloud.service.resource.huoshan.models import HuoshanLongTextTTSConfig, HuoshanOpenAPIConfig

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from backend.app.cloud.model import CloudSong

STORY_AUDIO_FORMAT = 'mp3'
STORY_TASK_STATUS_PENDING = 0
STORY_TASK_STATUS_PROCESSING = 1
STORY_TASK_STATUS_COMPLETED = 2
STORY_TASK_STATUS_FAILED = 3
STORY_AUDIO_PARAMS = {
    'format': STORY_AUDIO_FORMAT,
    'sample_rate': 24000,
    'speech_rate': 0,
    'loudness_rate': 0,
    'enable_timestamp': False,
}


class HuoshanVoiceService:
    STORY_SYNTHESIS_TASK_CACHE_PREFIX = 'fba:huoshan:story:synthesis'
    STORY_GENERATE_TASK_CACHE_PREFIX = 'fba:huoshan:story:generate'
    STORY_SCRIPT_TASK_CACHE_PREFIX = 'fba:huoshan:story:script'
    ROLE_STORY_SCRIPT_SYSTEM_PROMPT = (
        '你是儿童故事对话编剧。'
        '请只使用提供的角色信息和用户要求创作故事台词，不要新增角色。'
        '故事要有自然的开头、推进、转折和结尾，整体完整，适合直接口播。'
        '每个角色的说话方式要符合自己的设定，台词之间要有互动感和推动情节的作用。'
        '语言要自然、顺口、适合朗读，避免空话、重复话、解释性废话。'
        '角色差异主要通过台词内容、情绪和互动体现，不要在台词里额外解释角色身份。'
        '不要写“科学家的我”“歌手的我”“冒险家的我”这类人设标签式表达，也不要用“某某的我”作为台词开头。'
        '只需要纯台词文本，不要加入“（轻声）”“（大声接）”“（欢快收尾）”这类括号提示。'
        '不要写“哼唱”“接唱”“合唱”“收尾”这类表演说明，也不要用引号包裹整句台词。'
        '如果用户要求“无C位”或“角色均衡”，各角色的出场和台词量要尽量均衡。'
        '除非用户另有要求，整体控制在 15 到 25 行。如果用户明确要求行数范围，必须优先严格满足。'
        '不要输出 Markdown，不要输出标题、说明、序号或 JSON。'
        '每一行只能是一句台词，格式必须是：[role_id]台词内容'
    )
    ROLE_STORY_SCRIPT_MARKER_RE = re.compile(r'\[(\d+)\]')
    ROLE_STORY_SCRIPT_LINE_RE = re.compile(r'^\[(\d+)\](.*)$')
    ROLE_STORY_SCRIPT_TEXT_PREFIX_RE = re.compile(r'^(?:[\(（][^()\n（）]{1,20}[\)）][\s:：,，、-]*)+')
    ROLE_STORY_SCRIPT_QUOTE_CHARS = '"\'“”‘’'

    def __init__(self) -> None:
        self._story_synthesis_tasks: dict[str, asyncio.Task[HuoshanStorySynthesisResult]] = {}
        self._story_generation_tasks: dict[str, asyncio.Task[HuoshanStoryGenerateResult]] = {}
        self._role_story_script_tasks: dict[str, asyncio.Task[HuoshanRoleStoryScriptTaskResult]] = {}

    @classmethod
    def _attach_voice_alias(cls, status: HuoshanVoiceStatus) -> HuoshanVoiceStatus:
        update_data: dict[str, str] = {}

        if not str(status.speaker_alias or '').strip():
            speaker_alias = get_voice_name(status.speaker_id)
            if speaker_alias is not None:
                update_data['speaker_alias'] = speaker_alias

        resource_id = cls._resolve_clone_voice_resource_id(status)
        if resource_id and resource_id != str(status.resource_id or '').strip():
            update_data['resource_id'] = resource_id

        if not update_data:
            return status
        return status.model_copy(update=update_data, deep=True)

    @staticmethod
    def _normalize_text(value: object) -> str:
        return str(value or '').strip()

    @staticmethod
    def _resolve_client_config() -> HuoshanOpenAPIConfig:
        return HuoshanOpenAPIConfig(
            access_key=settings.BYTES_OPENAPI_ACCESS_KEY.strip(),
            secret_key=settings.BYTES_OPENAPI_SECRET_KEY.get_secret_value().strip(),
            host=settings.BYTES_OPENAPI_HOST.strip(),
            region=settings.BYTES_OPENAPI_REGION.strip(),
            service=settings.BYTES_OPENAPI_SERVICE.strip(),
            version=settings.BYTES_OPENAPI_VERSION.strip(),
            timeout=settings.BYTES_OPENAPI_TIMEOUT_SECONDS,
        )

    @classmethod
    def _resolve_story_client_config(
            cls,
            speaker: str | None = None,
            *,
            resource_id: str | None = None,
    ) -> HuoshanLongTextTTSConfig:
        project = get_voice_project_for_speaker(speaker)
        resolved_resource_id = cls._normalize_text(resource_id) or CLONE_VOICE_RESOURCE_ID_V2
        query_resource_id = (
                settings.BYTES_TTS_LONG_QUERY_RESOURCE_ID.strip()
                or HuoshanLongTextTTSClient.infer_query_resource_id(resolved_resource_id)
        )
        return HuoshanLongTextTTSConfig(
            app_id=project.app_id,
            access_key=project.access_token,
            resource_id=resolved_resource_id,
            query_resource_id=query_resource_id,
            submit_url=settings.BYTES_TTS_LONG_SUBMIT_URL,
            query_url=settings.BYTES_TTS_LONG_QUERY_URL,
            timeout=settings.BYTES_TTS_LONG_TIMEOUT_SECONDS,
        )

    @classmethod
    def _create_openapi_client(cls) -> HuoshanOpenAPIClient:
        return HuoshanOpenAPIClient(cls._resolve_client_config())

    @classmethod
    def _create_story_client(
            cls,
            speaker: str | None = None,
            *,
            resource_id: str | None = None,
    ) -> HuoshanLongTextTTSClient:
        return HuoshanLongTextTTSClient(cls._resolve_story_client_config(speaker, resource_id=resource_id))

    @classmethod
    def _resolve_story_voice(
            cls,
            *,
            speaker: str,
            voice_status: HuoshanVoiceStatus | None = None,
    ) -> tuple[VoiceProfile, HuoshanVoiceStatus | None]:
        public_voice = get_public_voice(speaker)
        if public_voice is not None:
            return public_voice, None

        if voice_status is None:
            raise errors.NotFoundError(msg='Voice clone does not exist')

        profile = get_voice_profile(voice_status.speaker_id or speaker)
        if profile is None:
            profile = VoiceProfile(
                id=cls._normalize_text(voice_status.speaker_id or speaker),
                name=cls._normalize_text(voice_status.speaker_alias),
            )
        return profile, voice_status

    @classmethod
    def _resolve_story_resource_id(cls, voice: VoiceProfile) -> str:
        return cls._normalize_text(voice.resource_id) or CLONE_VOICE_RESOURCE_ID_V2

    @classmethod
    def _resolve_clone_voice_resource_id(cls, status: HuoshanVoiceStatus) -> str:
        for detail in status.model_type_details:
            resource_id = cls._normalize_text(detail.resource_id)
            if resource_id:
                return resource_id
        return CLONE_VOICE_RESOURCE_ID_V2

    @staticmethod
    def _story_generation_system_prompt() -> str:
        return (
            '你是儿童睡前故事写作助手，擅长创作适合 2 到 6 岁儿童聆听的中文晚安故事。'
            '你的文字要像温柔的大人坐在床边轻声讲述，细腻、安静、柔软，适合直接做 TTS 口播。'
        )

    @staticmethod
    def _build_story_generation_prompt(topic: str) -> str:
        normalized_topic = topic.strip()
        return (
            '请围绕以下主题创作一篇中文睡前故事，直接输出故事正文，不要输出标题、说明、Markdown、分点或额外前后缀。'
            '写作要求：'
            '1. 采用温柔、轻声、安抚式的讲述口吻，像月亮妈妈在床边讲故事。'
            '2. 以第二人称或亲昵称呼和孩子说话，让孩子有被陪伴的感觉。'
            '3. 从一个小而具体的生活意象展开想象，比如小脚丫、小被子、小枕头、小月亮、小手、小雨声。'
            '4. 多写触觉、温度、声音、气味、动作等细节，要有画面感和身体感。'
            '5. 句子尽量短一点，段落尽量短一点，节奏轻柔，适合幼儿睡前聆听。'
            '6. 可以适度使用重复、拟声和轻微停顿，让语言更有安抚感。'
            '7. 不要出现激烈冲突、说教、知识讲解、成人化表达或过度复杂情节。'
            '8. 结尾要自然收束到安静、放松、入睡的状态。'
            '9. 长度控制在 700 到 1000 字。'
            f'主题：{normalized_topic}'
        )

    @classmethod
    def _build_role_story_script_prompt(
            cls,
            *,
            roles: list[HuoshanRoleStoryRoleInfo],
            text: str,
    ) -> str:
        role_payload = json.dumps([role.model_dump(mode='json') for role in roles], ensure_ascii=False)
        return (
            f'可用角色如下：\n{role_payload}\n\n'
            f'用户要求如下：\n{text}\n\n'
            '请基于以上角色设定和用户要求，创作一个完整的小故事对话。'
            '要求如下：'
            '1. 只允许使用提供的 role_id。'
            '2. 每行只写一条角色台词。'
            '3. 每条台词必须严格使用格式：[role_id]台词内容'
            '4. 台词要体现角色性格、情绪和彼此互动，但不要在台词里自我标注身份。'
            '5. 不要出现“科学家的我”“歌手的我”“冒险家的我”这类表达，也不要用“某某的我”作为开场白。'
            '6. 只输出纯台词，不要加“（轻声）”“（大声接）”“（欢快收尾）”这类括号提示，不要写哼唱、接唱、合唱等表演说明。'
            '7. 不要用引号包裹整句台词。'
            '8. 故事要有起承转合，结尾要完整，不要突然结束。'
            '9. 如果要求无C位或角色均衡，请尽量平均分配台词。'
            '10. 不要输出标题、旁白说明、序号、Markdown 或任何额外内容。'
            '输出示例：\n'
            '[1]今天的风好轻呀，我们一起去看看山那边发生了什么吧。'
        )

    @classmethod
    def _sanitize_role_story_script_text(cls, text: object) -> str:
        normalized = str(text or '').strip()
        if not normalized:
            return ''

        normalized = cls.ROLE_STORY_SCRIPT_TEXT_PREFIX_RE.sub('', normalized).strip()
        if len(normalized) >= 2:
            if normalized[0] in cls.ROLE_STORY_SCRIPT_QUOTE_CHARS and normalized[-1] in cls.ROLE_STORY_SCRIPT_QUOTE_CHARS:
                normalized = normalized[1:-1].strip()
        return normalized

    @staticmethod
    def _split_role_story_script_buffer(buffer: str) -> tuple[list[str], str]:
        normalized = str(buffer or '').replace('\r\n', '\n').replace('\r', '\n')
        if not normalized:
            return [], ''

        complete_lines: list[str] = []
        cursor = 0

        while True:
            current_match = HuoshanVoiceService.ROLE_STORY_SCRIPT_MARKER_RE.search(normalized, cursor)
            if current_match is None:
                return complete_lines, normalized[cursor:]

            start = current_match.start()
            prefix = normalized[cursor:start]
            if prefix.strip():
                raise errors.GatewayError(msg=f'Story script generation returned invalid content: {prefix.strip()}')

            next_match = HuoshanVoiceService.ROLE_STORY_SCRIPT_MARKER_RE.search(normalized, start + 1)
            next_marker_pos = next_match.start() if next_match is not None else -1
            newline_pos = normalized.find('\n', start)

            delimiter_positions = [position for position in (next_marker_pos, newline_pos) if position != -1]
            if not delimiter_positions:
                return complete_lines, normalized[start:]

            end = min(delimiter_positions)
            complete_lines.append(normalized[start:end])

            if end == newline_pos:
                cursor = newline_pos + 1
            else:
                cursor = end

    @classmethod
    def _parse_role_story_script_line(
            cls,
            line: str,
            *,
            role_ids: set[int],
            allow_empty_text: bool = False,
    ) -> HuoshanRoleStoryScriptLine | None:
        normalized = str(line or '').strip()
        if not normalized:
            return None

        match = cls.ROLE_STORY_SCRIPT_LINE_RE.match(normalized)
        if match is None:
            raise errors.GatewayError(msg=f'Story script generation returned invalid line format: {normalized}')

        role_id = int(match.group(1))
        if role_id not in role_ids:
            raise errors.GatewayError(msg=f'Story script generation returned unexpected role ID: {role_id}')

        text = cls._sanitize_role_story_script_text(match.group(2))
        if not text:
            if allow_empty_text:
                return None
            raise errors.GatewayError(msg=f'Story script generation returned empty line content: {normalized}')

        return HuoshanRoleStoryScriptLine(role_id=role_id, text=text)

    @classmethod
    def _parse_role_story_script_lines(
            cls,
            lines: list[str],
            *,
            role_ids: set[int],
    ) -> list[HuoshanRoleStoryScriptLine]:
        parsed_lines: list[HuoshanRoleStoryScriptLine] = []
        for line in lines:
            parsed_line = cls._parse_role_story_script_line(line, role_ids=role_ids, allow_empty_text=True)
            if parsed_line is not None:
                parsed_lines.append(parsed_line)
        return parsed_lines

    @classmethod
    def _normalize_role_story_script_lines(
            cls,
            lines: list[HuoshanRoleStoryScriptLine],
            *,
            role_ids: set[int],
    ) -> list[HuoshanRoleStoryScriptLine]:
        if not lines:
            return []

        raw_content = '\n'.join(f'[{line.role_id}]{line.text}' for line in lines)
        raw_lines, buffer = cls._split_role_story_script_buffer(f'{raw_content}\n')
        normalized_lines = cls._parse_role_story_script_lines(raw_lines, role_ids=role_ids)

        trailing_line = cls._parse_role_story_script_line(buffer, role_ids=role_ids, allow_empty_text=True)
        if trailing_line is not None:
            normalized_lines.append(trailing_line)

        return normalized_lines

    @classmethod
    def _normalize_role_story_script_task_result(
            cls,
            result: HuoshanRoleStoryScriptTaskResult,
    ) -> HuoshanRoleStoryScriptTaskResult:
        normalized_lines = cls._normalize_role_story_script_lines(list(result.lines), role_ids=set(result.role_ids))
        return result.model_copy(update={'lines': normalized_lines}, deep=True)

    @staticmethod
    def _validate_role_story_script_completion(
            lines: list[HuoshanRoleStoryScriptLine],
            *,
            role_ids: list[int],
    ) -> None:
        if not lines:
            raise errors.GatewayError(msg='Story script generation returned an empty script list')

        used_role_ids = {item.role_id for item in lines}
        missing_role_ids = [role_id for role_id in role_ids if role_id not in used_role_ids]
        if missing_role_ids:
            raise errors.GatewayError(
                msg=f'Story script generation did not use all requested roles: {", ".join(str(role_id) for role_id in missing_role_ids)}'
            )

    @staticmethod
    def _build_error_data(exc: HuoshanAPIError) -> dict[str, object]:
        return {
            'status_code': exc.status_code,
            'code': exc.code,
            'request_id': exc.request_id,
            'payload': exc.payload,
        }

    @classmethod
    def _raise_api_error(cls, exc: HuoshanAPIError) -> None:
        data = cls._build_error_data(exc)
        status_code = exc.status_code
        log.error(f'Huoshan API error: {exc}; data={data}')

        if status_code == 404:
            raise errors.NotFoundError(msg=exc.message, data=data) from exc
        if status_code == 409:
            raise errors.ConflictError(msg=exc.message, data=data) from exc
        if 400 <= status_code < 500:
            raise errors.RequestError(code=status_code, msg=exc.message, data=data) from exc
        raise errors.GatewayError(msg=exc.message, data=data) from exc

    @staticmethod
    def _build_story_payload(obj: HuoshanStorySynthesisParam, *, uid: str) -> dict[str, object]:
        return {
            'user': {'uid': uid},
            'unique_id': uuid.uuid4().hex,
            'namespace': 'BidirectionalTTS',
            'req_params': {
                'text': str(obj.story_content).replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' '),
                'speaker': obj.speaker,
                'audio_params': {
                    **STORY_AUDIO_PARAMS,
                    'speech_rate': int(obj.speech_rate),
                    'loudness_rate': int(obj.loudness_rate),
                },
            },
        }

    @staticmethod
    def _clean_path_segment(value: str) -> str:
        cleaned: list[str] = []
        previous_dash = False

        for char in value.strip().lower():
            if char.isascii() and char.isalnum():
                cleaned.append(char)
                previous_dash = False
                continue
            if char in ('-', '_'):
                if not previous_dash:
                    cleaned.append('-')
                    previous_dash = True
                continue
            if not previous_dash:
                cleaned.append('-')
                previous_dash = True

        return ''.join(cleaned).strip('-') or 'story'

    @classmethod
    def _build_story_oss_key(cls, *, task_id: str) -> str:
        prefix = 'cloud/huoshan'
        filename = cls._clean_path_segment(f'icl-{task_id}')
        date_path = timezone.now().strftime('%Y%m%d')
        return str(PurePosixPath(prefix) / date_path / f'{filename}.{STORY_AUDIO_FORMAT}')

    @staticmethod
    async def _upload_story_audio(*, key: str, data: bytes) -> str:
        return await oss_client.upload_bytes(key=key, data=data)

    @staticmethod
    async def _get_bgm_song(db: AsyncSession, bgm_song_id: int) -> CloudSong:
        song = await cloud_song_service.get_song(db=db, pk=bgm_song_id)
        if not song.play_url:
            raise errors.RequestError(msg='Background music play URL is missing')
        return song

    @classmethod
    def _story_synthesis_task_key(cls, task_id: str) -> str:
        return f'{cls.STORY_SYNTHESIS_TASK_CACHE_PREFIX}:{task_id}'

    @classmethod
    def _story_generate_task_key(cls, task_id: str) -> str:
        return f'{cls.STORY_GENERATE_TASK_CACHE_PREFIX}:{task_id}'

    @classmethod
    def _role_story_script_task_key(cls, task_id: str) -> str:
        return f'{cls.STORY_SCRIPT_TASK_CACHE_PREFIX}:{task_id}'

    @staticmethod
    def _story_task_ttl_seconds() -> int:
        return max(int(settings.CACHE_REDIS_TTL), int(settings.BYTES_TTS_LONG_QUERY_TIMEOUT_SECONDS))

    @classmethod
    async def _save_story_synthesis_task_result(cls, result: HuoshanStorySynthesisResult) -> None:
        try:
            await redis_client.set(
                cls._story_synthesis_task_key(result.task_id),
                result.model_dump_json(),
                ex=cls._story_task_ttl_seconds(),
            )
        except Exception as exc:
            raise errors.GatewayError(msg='Failed to save Huoshan story task result') from exc

    @classmethod
    async def _get_story_synthesis_task_result(cls, task_id: str) -> HuoshanStorySynthesisResult:
        try:
            payload_raw = await redis_client.get(cls._story_synthesis_task_key(task_id))
        except Exception as exc:
            raise errors.GatewayError(msg='Failed to load Huoshan story task result') from exc

        if not payload_raw:
            raise errors.NotFoundError(msg=f'Huoshan story task not found, task_id={task_id}')
        return HuoshanStorySynthesisResult.model_validate_json(payload_raw)

    @classmethod
    async def _save_story_generate_task_result(cls, result: HuoshanStoryGenerateResult) -> None:
        try:
            await redis_client.set(
                cls._story_generate_task_key(result.task_id),
                result.model_dump_json(),
                ex=cls._story_task_ttl_seconds(),
            )
        except Exception as exc:
            raise errors.GatewayError(msg='Failed to save Huoshan story generation task result') from exc

    @classmethod
    async def _get_story_generate_task_result(cls, task_id: str) -> HuoshanStoryGenerateResult:
        try:
            payload_raw = await redis_client.get(cls._story_generate_task_key(task_id))
        except Exception as exc:
            raise errors.GatewayError(msg='Failed to load Huoshan story generation task result') from exc

        if not payload_raw:
            raise errors.NotFoundError(msg=f'Huoshan story generation task not found, task_id={task_id}')
        return HuoshanStoryGenerateResult.model_validate_json(payload_raw)

    @classmethod
    async def _save_role_story_script_task_result(cls, result: HuoshanRoleStoryScriptTaskResult) -> None:
        result = cls._normalize_role_story_script_task_result(result)
        try:
            await redis_client.set(
                cls._role_story_script_task_key(result.task_id),
                result.model_dump_json(),
                ex=cls._story_task_ttl_seconds(),
            )
        except Exception as exc:
            raise errors.GatewayError(msg='Failed to save Huoshan role story script task result') from exc

    @classmethod
    async def _get_role_story_script_task_result(cls, task_id: str) -> HuoshanRoleStoryScriptTaskResult:
        try:
            payload_raw = await redis_client.get(cls._role_story_script_task_key(task_id))
        except Exception as exc:
            raise errors.GatewayError(msg='Failed to load Huoshan role story script task result') from exc

        if not payload_raw:
            raise errors.NotFoundError(msg=f'Huoshan role story script task not found, task_id={task_id}')
        return cls._normalize_role_story_script_task_result(HuoshanRoleStoryScriptTaskResult.model_validate_json(payload_raw))

    @classmethod
    def _to_public_role_story_script_result(
            cls,
            result: HuoshanRoleStoryScriptTaskResult,
    ) -> HuoshanRoleStoryScriptResult:
        result = cls._normalize_role_story_script_task_result(result)
        return HuoshanRoleStoryScriptResult.model_validate(result.model_dump(exclude={'roles'}))

    def _start_story_synthesis_processing(self, task_id: str) -> None:
        current_task = self._story_synthesis_tasks.get(task_id)
        if current_task is not None and not current_task.done():
            return

        task = asyncio.create_task(
            self._process_story_synthesis(task_id),
            name=f'huoshan-story-synthesis-{task_id}',
        )
        self._story_synthesis_tasks[task_id] = task

        def _cleanup(done_task: asyncio.Task[HuoshanStorySynthesisResult]) -> None:
            if self._story_synthesis_tasks.get(task_id) is done_task:
                self._story_synthesis_tasks.pop(task_id, None)

        task.add_done_callback(_cleanup)

    def _start_story_generation_processing(self, task_id: str) -> None:
        current_task = self._story_generation_tasks.get(task_id)
        if current_task is not None and not current_task.done():
            return

        task = asyncio.create_task(
            self._process_story_generation(task_id),
            name=f'huoshan-story-generate-{task_id}',
        )
        self._story_generation_tasks[task_id] = task

        def _cleanup(done_task: asyncio.Task[HuoshanStoryGenerateResult]) -> None:
            if self._story_generation_tasks.get(task_id) is done_task:
                self._story_generation_tasks.pop(task_id, None)

        task.add_done_callback(_cleanup)

    def _start_role_story_script_processing(self, task_id: str) -> None:
        current_task = self._role_story_script_tasks.get(task_id)
        if current_task is not None and not current_task.done():
            return

        task = asyncio.create_task(
            self._process_role_story_script(task_id),
            name=f'huoshan-story-script-{task_id}',
        )
        self._role_story_script_tasks[task_id] = task

        def _cleanup(done_task: asyncio.Task[HuoshanRoleStoryScriptTaskResult]) -> None:
            if self._role_story_script_tasks.get(task_id) is done_task:
                self._role_story_script_tasks.pop(task_id, None)

        task.add_done_callback(_cleanup)

    async def _get_voice_status(self, *, speaker: str) -> HuoshanVoiceStatus:
        project_name = get_voice_project_for_speaker(speaker).name
        result = await self._list_clone_voice_status_page(
            HuoshanVoiceListParam(project_name=project_name, speaker_ids=[speaker], state=None, page_size=10)
        )
        for status in result.statuses:
            if status.speaker_id == speaker:
                if status.state not in ('Success', 'Active'):
                    raise errors.RequestError(msg=f'Voice clone is not available, current state={status.state}')
                return self._attach_voice_alias(status)
        raise errors.NotFoundError(msg='Voice clone does not exist')

    @classmethod
    async def _mix_story_audio(
            cls,
            *,
            speech_audio: bytes,
            bgm_play_url: str,
            bgm_volume: int,
    ) -> bytes:
        with TemporaryDirectory(prefix='huoshan_story_') as temp_dir:
            speech_path = Path(temp_dir) / f'speech.{STORY_AUDIO_FORMAT}'
            output_path = Path(temp_dir) / f'mixed.{STORY_AUDIO_FORMAT}'

            speech_path.write_bytes(speech_audio)
            await asyncio.to_thread(
                mix_audio_with_bgm,
                speech_path,
                bgm_play_url,
                output_path,
                bgm_volume=max(0.0, min(float(bgm_volume) / 100.0, 1.0)),
            )
            return output_path.read_bytes()

    async def _list_clone_voice_status_page(self, obj: HuoshanVoiceListParam) -> HuoshanVoiceListResult:
        if obj.speaker_id and (not obj.project_name or obj.project_name == 'default'):
            obj = obj.model_copy(update={'project_name': get_voice_project_for_speaker(obj.speaker_id).name}, deep=True)

        client = self._create_openapi_client()
        payload = obj.model_dump(exclude_none=True)

        try:
            data = await client.batch_list_mega_tts_train_status(payload)
        except HuoshanOpenAPIError as exc:
            self._raise_api_error(exc)
            raise
        finally:
            await client.close()

        return HuoshanVoiceListResult.model_validate(data.get('result') or {})

    async def list_clone_voice_statuses(self, obj: HuoshanVoiceListParam) -> list[HuoshanVoiceStatus]:
        query = obj.model_copy(deep=True)
        if query.page_size is None:
            query.page_size = 100
        if query.page_number is None:
            query.page_number = 1
        if query.state is None:
            query.state = 'Success'

        result = await self._list_clone_voice_status_page(query)
        return [self._attach_voice_alias(status) for status in result.statuses]

    async def _process_role_story_script(
            self,
            task_id: str,
    ) -> HuoshanRoleStoryScriptTaskResult:
        result = await self._get_role_story_script_task_result(task_id)
        allowed_role_ids = set(result.role_ids)
        buffer = ''
        lines = list(result.lines)

        try:
            async for chunk in doubao_provider.stream_chat(
                    [
                        {'role': 'system', 'content': self.ROLE_STORY_SCRIPT_SYSTEM_PROMPT},
                        {'role': 'user',
                         'content': self._build_role_story_script_prompt(roles=list(result.roles), text=result.text)},
                    ],
                    model_name=result.model,
                    reasoning_effort='minimal',
                    temperature=0.8,
            ):
                buffer += chunk
                raw_lines, buffer = self._split_role_story_script_buffer(buffer)
                parsed_lines = self._parse_role_story_script_lines(raw_lines, role_ids=allowed_role_ids)
                if not parsed_lines:
                    continue
                lines.extend(parsed_lines)
                result = result.model_copy(update={'lines': list(lines)}, deep=True)
                await self._save_role_story_script_task_result(result)

            trailing_line = self._parse_role_story_script_line(buffer, role_ids=allowed_role_ids)
            if trailing_line is not None:
                lines.append(trailing_line)

            self._validate_role_story_script_completion(lines, role_ids=result.role_ids)
            result = result.model_copy(update={
                'lines': list(lines),
                'is_completed': True,
                'task_status': STORY_TASK_STATUS_COMPLETED,
                'error_message': None,
            }, deep=True)
            await self._save_role_story_script_task_result(result)
            log.info(
                f'Huoshan role story script generation completed: task_id={task_id}, role_ids={result.role_ids}, '
                f'text={result.text!r}'
            )
            return result
        except Exception as exc:
            log.error(f'Huoshan role story script generation failed: task_id={task_id}, error={exc!r}')
            result = result.model_copy(update={
                'task_status': STORY_TASK_STATUS_FAILED,
                'error_message': getattr(exc, 'msg', None) or str(exc),
            }, deep=True)
            await self._save_role_story_script_task_result(result)
            return result

    async def _generate_story_content_once(
            self,
            *,
            client: AsyncOpenAI,
            model_name: str,
            topic: str,
    ) -> str:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    'role': 'system',
                    'content': self._story_generation_system_prompt(),
                },
                {
                    'role': 'user',
                    'content': self._build_story_generation_prompt(topic),
                },
            ],
            temperature=0.8,
        )

        story_content = str((response.choices[0].message.content if response.choices else '') or '').strip()
        if not story_content:
            raise errors.GatewayError(msg='Doubao story generation returned empty content')
        return story_content

    async def _process_story_generation(self, task_id: str) -> HuoshanStoryGenerateResult:
        result = await self._get_story_generate_task_result(task_id)
        client: AsyncOpenAI | None = None

        try:
            client = create_async_doubao_client()
            story_content = await self._generate_story_content_once(
                client=client,
                model_name=result.model,
                topic=result.topic,
            )
            result = result.model_copy(update={
                'story_content': story_content,
                'is_completed': True,
                'task_status': STORY_TASK_STATUS_COMPLETED,
                'error_message': None,
            }, deep=True)
            await self._save_story_generate_task_result(result)
            log.info(f'Huoshan story generation completed: task_id={task_id}, topic={result.topic!r}')
            return result
        except Exception as exc:
            log.error(f'Huoshan story generation failed: task_id={task_id}, error={exc!r}')
            result = result.model_copy(update={
                'task_status': STORY_TASK_STATUS_FAILED,
                'error_message': getattr(exc, 'msg', None) or str(exc),
            }, deep=True)
            await self._save_story_generate_task_result(result)
            return result
        finally:
            if client is not None:
                await client.close()

    async def submit_story_generation(self, obj: HuoshanStoryGenerateParam) -> HuoshanStoryGenerateResult:
        result = HuoshanStoryGenerateResult(
            task_id=uuid.uuid4().hex,
            topic=obj.topic.strip(),
            model=DEFAULT_DOUBAO_STORY_MODEL,
            story_content=None,
            is_completed=False,
            task_status=STORY_TASK_STATUS_PROCESSING,
            error_message=None,
        )
        await self._save_story_generate_task_result(result)
        self._start_story_generation_processing(result.task_id)
        log.info(f'Huoshan story generation submitted: task_id={result.task_id}, topic={result.topic!r}')
        return result

    async def get_story_generation(self, *, task_id: str) -> HuoshanStoryGenerateResult:
        return await self._get_story_generate_task_result(task_id)

    async def submit_role_story_script(
            self,
            *,
            db: AsyncSession,
            obj: HuoshanRoleStoryScriptParam,
    ) -> HuoshanRoleStoryScriptResult:
        roles = await cloud_role_service.get_roles_by_ids(db=db, role_ids=obj.role_ids)
        task_result = HuoshanRoleStoryScriptTaskResult(
            task_id=uuid.uuid4().hex,
            role_ids=list(obj.role_ids),
            text=obj.text,
            model=DEFAULT_DOUBAO_STORY_MODEL,
            lines=[],
            is_completed=False,
            task_status=STORY_TASK_STATUS_PROCESSING,
            error_message=None,
            roles=[
                HuoshanRoleStoryRoleInfo(
                    role_id=int(role.id),
                    name=str(role.name or '').strip(),
                    summary=str(role.summary or '').strip(),
                    system_prompt=str(role.system_prompt or '').strip(),
                )
                for role in roles
            ],
        )
        await self._save_role_story_script_task_result(task_result)
        self._start_role_story_script_processing(task_result.task_id)
        log.info(
            f'Huoshan role story script generation submitted: task_id={task_result.task_id}, '
            f'role_ids={task_result.role_ids}, text={task_result.text!r}'
        )
        return self._to_public_role_story_script_result(task_result)

    async def get_role_story_script(self, *, task_id: str) -> HuoshanRoleStoryScriptResult:
        result = await self._get_role_story_script_task_result(task_id)
        return self._to_public_role_story_script_result(result)

    async def _finalize_story_synthesis(
            self,
            *,
            current_result: HuoshanStorySynthesisResult,
            client: HuoshanLongTextTTSClient,
    ) -> HuoshanStorySynthesisResult:
        task_id = current_result.task_id
        source_audio_url = str(current_result.source_audio_url or '').strip()
        if not source_audio_url:
            raise errors.GatewayError(
                msg='Huoshan story synthesis succeeded but no audio URL was returned',
                data={'task_id': task_id},
            )

        speech_audio = await client.download_file(url=source_audio_url)
        output_audio = speech_audio
        if current_result.bgm is not None:
            output_audio = await self._mix_story_audio(
                speech_audio=speech_audio,
                bgm_play_url=current_result.bgm.play_url,
                bgm_volume=current_result.bgm_volume,
            )

        oss_key = self._build_story_oss_key(task_id=task_id)
        download_url = await self._upload_story_audio(key=oss_key, data=output_audio)
        if not download_url:
            raise errors.GatewayError(
                msg='Failed to upload story audio to OSS',
                data={'task_id': task_id, 'oss_key': oss_key},
            )

        result = current_result.model_copy(update={
            'task_status': STORY_TASK_STATUS_COMPLETED,
            'is_completed': True,
            'oss_key': oss_key,
            'download_url': download_url,
            'source_audio_url': source_audio_url,
            'error_message': None,
        }, deep=True)

        log.info(
            f'Huoshan story synthesized successfully: task_id={task_id}, speaker={current_result.speaker}, '
            f'bgm_song_id={current_result.bgm.song_id if current_result.bgm is not None else None}, oss_key={oss_key}'
        )
        return result

    async def _process_story_synthesis(self, task_id: str) -> HuoshanStorySynthesisResult:
        result = await self._get_story_synthesis_task_result(task_id)
        client = self._create_story_client(result.speaker, resource_id=result.resource_id)
        deadline = monotonic() + settings.BYTES_TTS_LONG_QUERY_TIMEOUT_SECONDS

        try:
            while True:
                query_response = await client.query(task_id=task_id)
                query_data = dict(query_response.get('data') or {})
                provider_task_status = int(query_data.get('task_status', 0))
                local_task_status = STORY_TASK_STATUS_PROCESSING
                if provider_task_status == 3:
                    local_task_status = STORY_TASK_STATUS_FAILED
                elif provider_task_status <= 0:
                    local_task_status = STORY_TASK_STATUS_PENDING

                result = result.model_copy(update={
                    'task_status': local_task_status,
                    'source_audio_url': str(query_data.get('audio_url') or '').strip() or None,
                    'sentences': list(query_data.get('sentences') or []),
                    'error_message': None,
                }, deep=True)
                await self._save_story_synthesis_task_result(result)

                if provider_task_status == 2:
                    result = await self._finalize_story_synthesis(
                        current_result=result,
                        client=client,
                    )
                    await self._save_story_synthesis_task_result(result)
                    return result

                if provider_task_status == 3:
                    log.error(
                        'Huoshan story synthesis provider returned failed status: '
                        f'task_id={task_id}, submit_request_id={result.submit_request_id}, '
                        f'speaker={result.speaker}, resource_id={result.resource_id}, '
                        f'query_resource_id={client.query_resource_id}, query_response={query_response}'
                    )
                    result = result.model_copy(update={
                        'task_status': STORY_TASK_STATUS_FAILED,
                        'error_message': 'Huoshan story synthesis task failed',
                    }, deep=True)
                    await self._save_story_synthesis_task_result(result)
                    return result

                if monotonic() >= deadline:
                    result = result.model_copy(update={
                        'task_status': STORY_TASK_STATUS_FAILED,
                        'error_message': f'Huoshan story synthesis task timed out, task_id={task_id}',
                    }, deep=True)
                    await self._save_story_synthesis_task_result(result)
                    return result

                await asyncio.sleep(settings.BYTES_TTS_LONG_QUERY_INTERVAL_SECONDS)
        except HuoshanTTSError as exc:
            log.error(
                'Huoshan story synthesis query failed: '
                f'task_id={task_id}, submit_request_id={result.submit_request_id}, '
                f'speaker={result.speaker}, resource_id={result.resource_id}, '
                f'query_resource_id={client.query_resource_id}, status_code={exc.status_code}, '
                f'code={exc.code}, query_request_id={exc.request_id}, payload={exc.payload}, error={exc!r}'
            )
            result = result.model_copy(update={
                'task_status': STORY_TASK_STATUS_FAILED,
                'error_message': exc.message,
            }, deep=True)
            await self._save_story_synthesis_task_result(result)
            return result
        except Exception as exc:
            log.error(f'Huoshan story synthesis processing failed: task_id={task_id}, error={exc!r}')
            result = result.model_copy(update={
                'task_status': STORY_TASK_STATUS_FAILED,
                'error_message': str(exc),
            }, deep=True)
            await self._save_story_synthesis_task_result(result)
            return result
        finally:
            await client.close()

    async def synthesize_story(
            self,
            *,
            db: AsyncSession,
            obj: HuoshanStorySynthesisParam,
    ) -> HuoshanStorySynthesisResult:
        bgm_song = None
        if obj.bgm_song_id is not None:
            bgm_song = await self._get_bgm_song(db, obj.bgm_song_id)
        public_voice = get_public_voice(obj.speaker)
        voice_status: HuoshanVoiceStatus | None = None
        if public_voice is None:
            voice_status = await self._get_voice_status(speaker=obj.speaker)

        voice_profile, resolved_voice_status = self._resolve_story_voice(
            speaker=obj.speaker,
            voice_status=voice_status,
        )
        resource_id = self._resolve_story_resource_id(voice_profile)
        story_client_config = self._resolve_story_client_config(obj.speaker, resource_id=resource_id)
        client = self._create_story_client(obj.speaker, resource_id=resource_id)

        try:
            submit_response = await client.submit(payload=self._build_story_payload(obj, uid=uuid.uuid4().hex))
        except HuoshanTTSError as exc:
            log.error(
                'Huoshan story synthesis submit failed: '
                f'speaker={obj.speaker}, submit_resource_id={resource_id}, error={exc}'
            )
            self._raise_api_error(exc)
            raise
        finally:
            await client.close()

        task_id = str((submit_response.get('data') or {}).get('task_id') or '').strip()
        submit_request_id = str(submit_response.get('_request_id') or '').strip() or None
        log.info(
            'Huoshan story synthesis submit response: '
            f'speaker={obj.speaker}, submit_resource_id={resource_id}, submit_request_id={submit_request_id}, '
            f'response={submit_response}'
        )
        if not task_id:
            raise errors.GatewayError(msg='Huoshan story synthesis did not return task_id', data=submit_response)

        result = HuoshanStorySynthesisResult(
            task_id=task_id,
            submit_request_id=submit_request_id,
            speaker=voice_profile.id,
            speaker_alias=(
                    resolved_voice_status.speaker_alias or voice_profile.name) if resolved_voice_status else voice_profile.name,
            speaker_state=resolved_voice_status.state if resolved_voice_status else None,
            resource_id=story_client_config.resource_id,
            audio_format=STORY_AUDIO_FORMAT,
            bgm=(
                HuoshanStoryBgmInfo(
                    song_id=bgm_song.id,
                    title=bgm_song.title,
                    play_url=str(bgm_song.play_url or '').strip(),
                    artist=bgm_song.artist,
                    duration=bgm_song.duration,
                )
                if bgm_song is not None else None
            ),
            bgm_volume=obj.bgm_volume if bgm_song is not None else 0,
            speech_rate=obj.speech_rate,
            loudness_rate=obj.loudness_rate,
            is_completed=False,
            task_status=STORY_TASK_STATUS_PROCESSING,
        )
        await self._save_story_synthesis_task_result(result)
        self._start_story_synthesis_processing(task_id)

        log.info(
            f'Huoshan story synthesis submitted: task_id={task_id}, submit_request_id={submit_request_id}, '
            f'speaker={obj.speaker}, bgm_song_id={bgm_song.id if bgm_song is not None else None}, '
            f'resource_id={story_client_config.resource_id}'
        )

        return result

    async def get_story_synthesis(self, *, task_id: str) -> HuoshanStorySynthesisResult:
        return await self._get_story_synthesis_task_result(task_id)


huoshan_voice_service = HuoshanVoiceService()


async def main():
    voice_status = await huoshan_voice_service._get_voice_status(speaker='S_7V2ryDOZ1')
    print(voice_status)


if __name__ == '__main__':
    asyncio.run(main())
