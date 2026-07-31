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
from contextlib import suppress

from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from typing import TYPE_CHECKING

from openai import AsyncOpenAI
from pydantic import ValidationError

from backend.app.cloud.schema.resource.huoshan import (
    HuoshanStreamTTSParam,
    HuoshanToyStoryToyInfo,
    HuoshanToyStoryScriptLine,
    HuoshanToyStoryScriptParam,
    HuoshanToyStoryScriptResult,
    HuoshanStoryGenerateParam,
    HuoshanStoryGenerateResult,
    HuoshanStoryBgmInfo,
    HuoshanStorySynthesisParam,
    HuoshanStorySynthesisResult,
    HuoshanVoiceListParam,
    HuoshanVoiceListResult,
    HuoshanVoiceStatus,
)
from backend.app.cloud.schema.resource.script import CreateScriptParam, ScriptLine
from backend.app.cloud.service.toy_service import toy_service
from backend.app.cloud.service.resource.song_service import cloud_song_service
from backend.app.cloud.service.resource.script_service import cloud_script_service
from backend.app.cloud.service.resource.huoshan.tts.tts_cache import tts_cache
from backend.app.cloud.service.resource.huoshan.tts.tts_stream import tts_stream_service
from backend.common.providers.ali_oss import oss_client
from backend.common.providers.doubao import DEFAULT_DOUBAO_LITE_MODEL, create_async_doubao_client, doubao_provider
from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.database.db import async_db_session
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
    TOY_STORY_SCRIPT_SYSTEM_PROMPT = (
        '你是儿童多玩偶对话故事编剧。'
        '你的任务不是写一组分别好听的台词，而是写一段真正发生交流的故事对话。'
        '每句台词都必须和上下文有关系，让人物之间像在接话、追问、回应、补充、安慰、提醒、商量或一起解决问题，而不是轮流各说各话。'
        '故事必须完整，包含明确的开场、推进、变化和收束。'
        '开场要尽快建立当前情境、目标、发现或问题，不要寒暄太久。'
        '中段要出现新的变化、小困难、小误会、新发现或小悬念，并通过对话继续推进。'
        '结尾要完成回应、解决、确认或情绪收束，不能在热闹处突然停止。'
        '大多数台词都应直接承接上一句中的对象、问题、动作、提议或情绪。'
        '允许少量台词主动抛出新信息，但抛出后，后续台词必须围绕这件事继续回应、追问、补充或处理。'
        '如果某句既不回应上一句，也不推进当前共同目标，这句就不应该出现。'
        '每个玩偶都要保留自身设定带来的说话习惯、关注点、情绪反应和处理方式。'
        '不同玩偶的差异要体现在内容和互动方式上，而不只是换一个 toy_id 重复同类句子。'
        '优先使用孩子熟悉的具体动作、感受、环境细节、小发现和小物件，少用抽象总结、说教和概念化表达。'
        '语言要自然、口语化、顺口、适合儿童听和直接口播。'
        '单句尽量简洁清楚，长短有变化，避免连续多句同句式、同节奏、同功能。'
        '避免空话、废话、重复解释、机械轮流发言和没有互动的独白堆叠。'
        '玩偶差异主要通过台词内容和互动体现，不要在台词里额外解释玩偶身份。'
        '不要写“科学家的我”“歌手的我”“冒险家的我”“某某的我”这类标签化表达。'
        '如果指定了 C 位玩偶，该玩偶要承担更多关键推进、核心情绪表达和结尾收束作用，但其他玩偶仍需自然参与，不能完全沦为陪衬。'
        '如果要求无 C 位或均衡分配，各玩偶的出场和台词量应尽量均衡。'
        '只输出纯台词。'
        '不要输出标题、说明、序号、旁白说明、Markdown、JSON 或任何额外内容。'
        '不要加入“（轻声）”“（大声接）”“（欢快收尾）”这类括号提示。'
        '不要写“哼唱”“接唱”“合唱”“收尾”这类表演说明。'
        '不要用引号包裹整句台词。'
        '每一行只能是一句台词，且必须严格使用格式：[toy_id]台词内容。'
    )
    TOY_STORY_SCRIPT_MARKER_RE = re.compile(r'\[(\d+)\]')
    TOY_STORY_SCRIPT_LINE_RE = re.compile(r'^\[(\d+)\](.*)$')
    TOY_STORY_SCRIPT_TEXT_PREFIX_RE = re.compile(r'^(?:[\(（][^()\n（）]{1,20}[\)）][\s:：,，、-]*)+')
    TOY_STORY_SCRIPT_QUOTE_CHARS = '"\'“”‘’'

    def __init__(self) -> None:
        self._story_synthesis_tasks: dict[str, asyncio.Task[HuoshanStorySynthesisResult]] = {}
        self._story_generation_tasks: dict[str, asyncio.Task[HuoshanStoryGenerateResult]] = {}
        self._toy_story_script_tasks: dict[str, asyncio.Task[HuoshanToyStoryScriptResult]] = {}

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
            '你是儿童睡前故事写作助手，擅长创作适合 2 到 6 岁儿童收听的中文晚安故事。'
            '你的文字要像温柔的大人坐在床边轻声讲述，细腻、安静、柔和，适合直接做 TTS 口播。'
        )

    @staticmethod
    def _build_story_generation_prompt(topic: str) -> str:
        normalized_topic = topic.strip()
        return (
            '请围绕以下主题创作一篇中文睡前故事，直接输出故事正文，不要输出标题、说明、Markdown、分点或额外前后缀。'
            '写作要求：'
            '1. 采用温柔、轻声、安抚式的讲述口吻，像月亮妈妈在床边讲故事。'
            '2. 以第二人称或亲昵称呼和孩子说话，让孩子有被陪伴的感觉。'
            '3. 从一个小而具体的生活意象展开想象，比如小被子、小枕头、小月亮、小雨声。'
            '4. 多写触觉、温度、声音、气味、动作等细节，要有画面感和身体感。'
            '5. 句子尽量短一点，段落尽量短一点，节奏轻柔，适合幼儿睡前聆听。'
            '6. 可以适度使用重复、拟声和轻微停顿，让语言更有安抚感。'
            '7. 不要出现激烈冲突、说教、知识讲解、成人化表达或过度复杂情节。'
            '8. 结尾要自然收束到安静、放松、入睡的状态。'
            '9. 长度控制在 700 到 1000 字。'
            f'主题：{normalized_topic}'
        )

    @classmethod
    def _build_toy_story_script_prompt(
            cls,
            *,
            toys: list[HuoshanToyStoryToyInfo],
            text: str,
            c_toy_id: int | None,
    ) -> str:
        """ 玩偶 AI-创作 """
        toy_payload = json.dumps([
            {
                'toy_id': toy.toy_id,
                'name': toy.name,
                'summary': cls._trim_toy_story_prompt_text(toy.summary, limit=120),
                'character_hint': cls._trim_toy_story_prompt_text(toy.system_prompt, limit=180),
            }
            for toy in toys
        ], ensure_ascii=False)
        center_prompt = (
            f'本次指定的 C 位玩偶是 [{c_toy_id}]，请优先让该玩偶承担开场引入、关键推进、情绪转折、结尾收束中的核心部分，但不要让其他玩偶完全边缘化，也不要让 C 位玩偶长期独白。'
            if c_toy_id is not None
            else '本次未指定 C 位玩偶，请按正常群像互动创作；如果用户要求无 C 位或均衡分配，请优先满足。'
        )
        return (
            f'可用玩偶如下：\n{toy_payload}\n\n'
            f'{center_prompt}\n\n'
            f'用户要求如下：\n{text}\n\n'
            '请基于以上玩偶设定和用户要求，创作一个完整的小故事对话。'
            '要求如下：'
            '1. 只允许使用提供的 toy_id。'
            '2. 只参考提供的 summary 和 character_hint 创作，不要照抄原文，不要把设定说明直接说出来。'
            '3. 每行只写一条玩偶台词，且必须严格使用格式：[toy_id]台词内容。'
            '4. 如果用户明确要求行数范围，必须优先满足；否则默认控制在 20 到 30 条 content 之间。'
            '5. 如果指定了 C 位玩偶，请让该玩偶承担更多关键推进和收束台词，但整体互动仍要自然。'
            '6. 如果要求无C位或玩偶均衡，请尽量平均分配普通玩偶的台词；如果存在旁白，旁白单独统计，不参与普通玩偶的均衡分配。'
            '7. 不要输出标题、旁白说明、序号、Markdown 或任何额外内容。'
            '输出示例：\n'
            '[1]今天的风好轻呀，我们一起去看看山那边发生了什么吧。'
        )

    @classmethod
    def _trim_toy_story_prompt_text(cls, value: object, *, limit: int) -> str:
        normalized = cls._normalize_text(value)
        if len(normalized) <= limit:
            return normalized
        return f'{normalized[:limit].rstrip()}...'

    @classmethod
    def _sanitize_toy_story_script_text(cls, text: object) -> str:
        normalized = str(text or '').strip()
        if not normalized:
            return ''

        normalized = cls.TOY_STORY_SCRIPT_TEXT_PREFIX_RE.sub('', normalized).strip()
        if len(normalized) >= 2:
            if normalized[0] in cls.TOY_STORY_SCRIPT_QUOTE_CHARS and normalized[-1] in cls.TOY_STORY_SCRIPT_QUOTE_CHARS:
                normalized = normalized[1:-1].strip()
        return normalized

    @staticmethod
    def _split_toy_story_script_buffer(buffer: str) -> tuple[list[str], str]:
        normalized = str(buffer or '').replace('\r\n', '\n').replace('\r', '\n')
        if not normalized:
            return [], ''

        complete_lines: list[str] = []
        cursor = 0

        while True:
            current_match = HuoshanVoiceService.TOY_STORY_SCRIPT_MARKER_RE.search(normalized, cursor)
            if current_match is None:
                return complete_lines, normalized[cursor:]

            start = current_match.start()
            prefix = normalized[cursor:start]
            if prefix.strip():
                raise errors.GatewayError(msg=f'Story script generation returned invalid content: {prefix.strip()}')

            next_match = HuoshanVoiceService.TOY_STORY_SCRIPT_MARKER_RE.search(normalized, start + 1)
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
    def _parse_toy_story_script_line(
            cls,
            line: str,
            *,
            toy_ids: set[int],
            allow_empty_text: bool = False,
    ) -> HuoshanToyStoryScriptLine | None:
        normalized = str(line or '').strip()
        if not normalized:
            return None

        match = cls.TOY_STORY_SCRIPT_LINE_RE.match(normalized)
        if match is None:
            raise errors.GatewayError(msg=f'Story script generation returned invalid line format: {normalized}')

        toy_id = int(match.group(1))
        if toy_id not in toy_ids:
            raise errors.GatewayError(msg=f'Story script generation returned unexpected toy ID: {toy_id}')

        text = cls._sanitize_toy_story_script_text(match.group(2))
        if not text:
            if allow_empty_text:
                return None
            raise errors.GatewayError(msg=f'Story script generation returned empty line content: {normalized}')

        return HuoshanToyStoryScriptLine(toy_id=toy_id, text=text)

    @classmethod
    def _parse_toy_story_script_lines(
            cls,
            lines: list[str],
            *,
            toy_ids: set[int],
    ) -> list[HuoshanToyStoryScriptLine]:
        parsed_lines: list[HuoshanToyStoryScriptLine] = []
        for line in lines:
            parsed_line = cls._parse_toy_story_script_line(line, toy_ids=toy_ids, allow_empty_text=True)
            if parsed_line is not None:
                parsed_lines.append(parsed_line)
        return parsed_lines

    @classmethod
    def _normalize_toy_story_script_lines(
            cls,
            lines: list[HuoshanToyStoryScriptLine],
            *,
            toy_ids: set[int],
    ) -> list[HuoshanToyStoryScriptLine]:
        if not lines:
            return []

        raw_content = '\n'.join(f'[{line.toy_id}]{line.text}' for line in lines)
        raw_lines, buffer = cls._split_toy_story_script_buffer(f'{raw_content}\n')
        normalized_lines = cls._parse_toy_story_script_lines(raw_lines, toy_ids=toy_ids)

        trailing_line = cls._parse_toy_story_script_line(buffer, toy_ids=toy_ids, allow_empty_text=True)
        if trailing_line is not None:
            normalized_lines.append(trailing_line)

        result_lines: list[HuoshanToyStoryScriptLine] = []
        for index, normalized_line in enumerate(normalized_lines):
            current_line = lines[index] if index < len(lines) else None
            if current_line is not None and current_line.toy_id == normalized_line.toy_id:
                normalized_line = normalized_line.model_copy(update={'tts_token': current_line.tts_token}, deep=True)
            result_lines.append(normalized_line)

        return result_lines

    @classmethod
    def _normalize_toy_story_script_result(
            cls,
            result: HuoshanToyStoryScriptResult,
    ) -> HuoshanToyStoryScriptResult:
        normalized_lines = cls._normalize_toy_story_script_lines(list(result.lines), toy_ids=set(result.toy_ids))
        return result.model_copy(update={'lines': normalized_lines}, deep=True)

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
    def _build_story_oss_key(*, task_id: str) -> str:
        date_path = timezone.now().strftime('%Y%m%d')
        return f'cloud/huoshan/{date_path}/icl-{task_id}.{STORY_AUDIO_FORMAT}'

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
    def _toy_story_script_task_key(cls, task_id: str) -> str:
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
    async def _save_toy_story_script_task_result(cls, result: HuoshanToyStoryScriptResult) -> None:
        normalized_result = cls._normalize_toy_story_script_result(result)
        try:
            await redis_client.set(
                cls._toy_story_script_task_key(normalized_result.task_id),
                normalized_result.model_dump_json(),
                ex=cls._story_task_ttl_seconds(),
            )
        except Exception as exc:
            raise errors.GatewayError(msg='Failed to save Huoshan toy story script task result') from exc

    @classmethod
    async def _get_toy_story_script_task_result(cls, task_id: str) -> HuoshanToyStoryScriptResult:
        try:
            payload_raw = await redis_client.get(cls._toy_story_script_task_key(task_id))
        except Exception as exc:
            raise errors.GatewayError(msg='Failed to load Huoshan toy story script task result') from exc

        if not payload_raw:
            raise errors.NotFoundError(msg=f'Huoshan toy story script task not found, task_id={task_id}')

        try:
            result = HuoshanToyStoryScriptResult.model_validate_json(payload_raw)
        except ValidationError:
            payload = json.loads(payload_raw)
            if not isinstance(payload, dict) or 'result' not in payload:
                raise

            result_payload = payload.get('result') or {}
            if isinstance(result_payload, dict) and payload.get('owner_id') is not None:
                result_payload = {**result_payload, 'owner_id': payload.get('owner_id')}
            result = HuoshanToyStoryScriptResult.model_validate(result_payload)

        return cls._normalize_toy_story_script_result(result)

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

    def _start_toy_story_script_processing(self, task_id: str) -> None:
        current_task = self._toy_story_script_tasks.get(task_id)
        if current_task is not None and not current_task.done():
            return

        task = asyncio.create_task(
            self._process_toy_story_script(task_id),
            name=f'huoshan-story-script-{task_id}',
        )
        self._toy_story_script_tasks[task_id] = task

        def _cleanup(done_task: asyncio.Task[HuoshanToyStoryScriptResult]) -> None:
            if self._toy_story_script_tasks.get(task_id) is done_task:
                self._toy_story_script_tasks.pop(task_id, None)

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

    @staticmethod
    async def _process_toy_story_script_tts_queue(
            queue: 'asyncio.Queue[tuple[str, HuoshanStreamTTSParam] | None]',
    ) -> None:
        while True:
            queue_item = await queue.get()
            if queue_item is None:
                return

            request_id, tts_param = queue_item
            await tts_stream_service.query_and_wait(obj=tts_param, request_id=request_id)

    async def _process_toy_story_script(
            self,
            task_id: str,
    ) -> HuoshanToyStoryScriptResult:
        result = await self._get_toy_story_script_task_result(task_id)
        allowed_toy_ids = set(result.toy_ids)
        toy_map = {toy.toy_id: toy for toy in result.toys}
        buffer = ''
        lines = list(result.lines)

        tts_queue: asyncio.Queue[tuple[str, HuoshanStreamTTSParam] | None] = asyncio.Queue()
        tts_worker = asyncio.create_task(
            self._process_toy_story_script_tts_queue(tts_queue),
            name=f'huoshan-story-script-tts-{task_id}',
        )

        async def _cancel_tts_worker() -> None:
            if not tts_worker.done():
                tts_worker.cancel()
            with suppress(Exception, asyncio.CancelledError):
                await tts_worker

        async def _process_line(_line: HuoshanToyStoryScriptLine) -> None:
            toy = toy_map.get(_line.toy_id)
            if toy is None:
                raise errors.GatewayError(msg=f'Toy info is missing for toy_id={_line.toy_id}')
            request_id = await tts_cache.create_new_request()
            lines.append(_line.model_copy(update={'tts_token': request_id}, deep=True))
            tts_queue.put_nowait(
                (
                    request_id,
                    HuoshanStreamTTSParam(
                        text=_line.text, speaker=toy.speaker, speech_rate=0, loudness_rate=0,
                    ),
                )
            )

        try:
            async for chunk in doubao_provider.stream_chat(
                    [
                        {'role': 'system', 'content': self.TOY_STORY_SCRIPT_SYSTEM_PROMPT},
                        {'role': 'user',
                         'content': self._build_toy_story_script_prompt(
                             toys=list(result.toys),
                             text=result.text,
                             c_toy_id=result.c_toy_id,
                         )},
                    ],
                    model_name=result.model,
                    reasoning_effort='minimal',
                    temperature=0.8,
            ):
                buffer += chunk
                raw_lines, buffer = self._split_toy_story_script_buffer(buffer)
                parsed_lines = self._parse_toy_story_script_lines(raw_lines, toy_ids=allowed_toy_ids)
                if not parsed_lines:
                    continue
                for parsed_line in parsed_lines:
                    await _process_line(parsed_line)
                result = result.model_copy(update={'lines': list(lines)}, deep=True)
                await self._save_toy_story_script_task_result(result)

            trailing_line = self._parse_toy_story_script_line(buffer, toy_ids=allowed_toy_ids)
            if trailing_line is not None:
                await _process_line(trailing_line)
                result = result.model_copy(update={'lines': list(lines)}, deep=True)
                await self._save_toy_story_script_task_result(result)

            tts_queue.put_nowait(None)
            await tts_worker
            result = result.model_copy(update={
                'is_completed': True,
                'task_status': STORY_TASK_STATUS_COMPLETED,
                'error_message': None,
            }, deep=True)
            await self._save_toy_story_script_task_result(result)
            asyncio.create_task(
                self._auto_save_toy_story_script(task_id=task_id),
                name=f'huoshan-story-script-save-{task_id}',
            )
            log.info(
                f'Huoshan toy story script generation completed: task_id={task_id}, toy_ids={result.toy_ids}, '
                f'text={result.text!r}'
            )
            return result
        except asyncio.CancelledError:
            log.warning(f'Huoshan toy story script generation cancelled: task_id={task_id}')
            await _cancel_tts_worker()
            result = result.model_copy(update={
                'task_status': STORY_TASK_STATUS_FAILED,
                'error_message': 'cancelled',
            }, deep=True)
            await self._save_toy_story_script_task_result(result)
            raise
        except Exception as exc:
            log.error(f'Huoshan toy story script generation failed: task_id={task_id}, error={exc!r}')
            await _cancel_tts_worker()
            result = result.model_copy(update={
                'task_status': STORY_TASK_STATUS_FAILED,
                'error_message': getattr(exc, 'msg', None) or str(exc),
            }, deep=True)
            await self._save_toy_story_script_task_result(result)
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
            model=DEFAULT_DOUBAO_LITE_MODEL,
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

    async def submit_toy_story_script(
            self,
            *,
            db: AsyncSession,
            obj: HuoshanToyStoryScriptParam,
            user_id: int,
    ) -> HuoshanToyStoryScriptResult:
        toys = await toy_service.get_toys_by_ids(db=db, toy_ids=obj.toy_ids)
        toy_infos: list[HuoshanToyStoryToyInfo] = []  # TODO: 旁白
        invalid_toys: list[str] = []
        for toy in toys:
            speaker = str(toy.voice_id or '').strip()
            if not speaker:
                invalid_toys.append(f'{int(toy.id)}:{str(toy.name or "").strip() or "Unnamed"}')
                continue
            toy_infos.append(
                HuoshanToyStoryToyInfo(
                    toy_id=int(toy.id),
                    name=str(toy.name or '').strip(),
                    summary=str(toy.summary or '').strip(),
                    system_prompt=str(toy.system_prompt or '').strip(),
                    speaker=speaker,
                    voice_name=str(toy.voice_name or get_voice_name(speaker) or '').strip(),
                )
            )

        if invalid_toys:
            raise errors.RequestError(msg=f'Toy voice_id is required for story playback: {", ".join(invalid_toys)}')

        task_result = HuoshanToyStoryScriptResult(
            task_id=uuid.uuid4().hex,
            toy_ids=list(obj.toy_ids),
            text=obj.text,
            c_toy_id=obj.c_toy_id,
            model=DEFAULT_DOUBAO_LITE_MODEL,
            toys=toy_infos,
            lines=[],
            owner_id=user_id,
            is_completed=False,
            task_status=STORY_TASK_STATUS_PROCESSING,
            error_message=None,
        )
        await self._save_toy_story_script_task_result(task_result)
        self._start_toy_story_script_processing(task_result.task_id)
        log.info(
            f'Huoshan toy story script generation submitted: task_id={task_result.task_id}, '
            f'toy_ids={task_result.toy_ids}, text={task_result.text!r}, user_id={user_id}'
        )
        return task_result

    async def get_toy_story_script(self, *, task_id: str, user_id: int) -> HuoshanToyStoryScriptResult:
        result = await self._get_toy_story_script_task_result(task_id)
        if result.owner_id != user_id:
            raise errors.NotFoundError(msg=f'Huoshan toy story script task not found, task_id={result.task_id}')
        return result

    @staticmethod
    async def _build_toy_story_script_content(result: HuoshanToyStoryScriptResult) -> list[ScriptLine]:
        content: list[ScriptLine] = []
        for line in result.lines:
            request_id = str(line.tts_token or '').strip()
            if not request_id:
                raise errors.GatewayError(
                    msg=f'Toy story script line is missing tts_token, task_id={result.task_id}, toy_id={line.toy_id}'
                )

            download_url = await tts_stream_service.upload_audio_to_oss(request_id=request_id)
            content.append(ScriptLine(toy_id=line.toy_id, text=line.text, audio_url=download_url))
        return content

    async def _auto_save_toy_story_script(
            self,
            *,
            task_id: str,
    ) -> None:
        result = await self._get_toy_story_script_task_result(task_id)

        try:
            async with async_db_session() as db:
                try:
                    content = await self._build_toy_story_script_content(result)
                    script = await cloud_script_service.create_script(
                        db=db,
                        obj=CreateScriptParam(
                            title=result.text,
                            summary=result.text,
                            cover_url=None,
                            author=None,
                            toy_ids=list(result.toy_ids),
                            content=content,
                            owner_id=result.owner_id,
                            status=0,
                            remark=None,
                        ),
                    )
                    await db.commit()
                    log.info(f'Huoshan toy story script auto saved: task_id={task_id}, script_id={script.id}')
                except Exception:
                    with suppress(Exception):
                        await db.rollback()
                    raise
        except Exception as exc:
            log.error(f'Huoshan toy story script auto save failed: task_id={task_id}, error={exc!r}')
            return

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
        download_url = await oss_client.upload_bytes(key=oss_key, data=output_audio)
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
