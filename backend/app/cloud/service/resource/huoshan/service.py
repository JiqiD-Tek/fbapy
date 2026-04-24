# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : service.py
@Author  : OpenAI
@Date    : 2026/04/13
"""

from __future__ import annotations

import asyncio
import uuid

from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from time import monotonic
from typing import TYPE_CHECKING

import httpx
from openai import AsyncOpenAI

from backend.app.cloud.schema.huoshan import (
    HuoshanStoryGenerateParam,
    HuoshanStoryGenerateResult,
    HuoshanStoryBgmInfo,
    HuoshanStorySynthesisParam,
    HuoshanStorySynthesisResult,
    HuoshanVoiceListParam,
    HuoshanVoiceListResult,
    HuoshanVoiceOrderParam,
    HuoshanVoiceOrderResponse,
    HuoshanVoiceRenewParam,
    HuoshanVoiceRenewResponse,
    HuoshanVoiceStatus,
)
from backend.app.cloud.service.resource.song_service import cloud_song_service
from backend.common.providers.ali_oss import oss_client
from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.database.redis import redis_client
from backend.utils.timezone import timezone

from backend.app.cloud.service.resource.huoshan.audio_tools import mix_audio_with_bgm
from backend.app.cloud.service.resource.huoshan.client import HuoshanLongTextTTSClient, HuoshanOpenAPIClient
from backend.app.cloud.service.resource.huoshan.exceptions import HuoshanAPIError, HuoshanOpenAPIError, HuoshanTTSError
from backend.app.cloud.service.resource.huoshan.models import HuoshanLongTextTTSConfig, HuoshanOpenAPIConfig

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.app.cloud.model import CloudSong

DEFAULT_DOUBAO_STORY_MODEL = 'doubao-seed-2-0-pro-260215'
DOUBAO_HTTP_TIMEOUT = httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=30.0)
DOUBAO_HTTP_LIMITS = httpx.Limits(max_connections=20, max_keepalive_connections=20, keepalive_expiry=120.0)
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
HUOSHAN_VOICE_REMARK_MAP = {
    'S_GKcK2x2X1': '曲老师',
    'S_EKcK2x2X1': '虾球',
    'S_DKcK2x2X1': '米粒',
    'S_CKcK2x2X1': '旁白',
    'S_BKcK2x2X1': '珍棒',
    'S_AKcK2x2X1': '珍居',
    'S_zKcK2x2X1': '凯叔',
    'S_yKcK2x2X1': '成男温柔',
    'S_xKcK2x2X1': '成女温柔',
    'S_FKcK2x2X1': '成女活泼',
    'S_7V2ryDOZ1': '汤普森爸爸',
}
HUOSHAN_JS61_SPEAKERS = frozenset({'S_7V2ryDOZ1'})


class HuoshanVoiceService:
    STORY_SYNTHESIS_TASK_CACHE_PREFIX = 'fba:huoshan:story:synthesis'
    STORY_GENERATE_TASK_CACHE_PREFIX = 'fba:huoshan:story:generate'

    def __init__(self) -> None:
        self._story_synthesis_tasks: dict[str, asyncio.Task[HuoshanStorySynthesisResult]] = {}
        self._story_generation_tasks: dict[str, asyncio.Task[HuoshanStoryGenerateResult]] = {}

    @staticmethod
    def _attach_voice_remark(status: HuoshanVoiceStatus) -> HuoshanVoiceStatus:
        speaker_id = (status.speaker_id or '').strip()
        speaker_remark = HUOSHAN_VOICE_REMARK_MAP.get(speaker_id)
        if speaker_remark is None:
            return status
        return status.model_copy(update={'speaker_remark': speaker_remark}, deep=True)

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

    @staticmethod
    def _resolve_story_tts_credentials(speaker: str | None = None) -> tuple[str, str]:
        speaker_id = str(speaker or '').strip()
        if (
                speaker_id in HUOSHAN_JS61_SPEAKERS
                and settings.JS61_BYTES_TTS_APPID.strip()
                and settings.JS61_BYTES_TTS_TOKEN.strip()
        ):
            return settings.JS61_BYTES_TTS_APPID.strip(), settings.JS61_BYTES_TTS_TOKEN.strip()

        return settings.BYTES_TTS_APPID.strip(), settings.BYTES_TTS_TOKEN.strip()

    @classmethod
    async def _get_project_name(cls, speaker: str | None = None):
        speaker_id = str(speaker or '').strip()
        return "JS61" if speaker_id in HUOSHAN_JS61_SPEAKERS else "default"

    @classmethod
    def _resolve_story_client_config(cls, speaker: str | None = None) -> HuoshanLongTextTTSConfig:
        app_id, access_key = cls._resolve_story_tts_credentials(speaker)
        resource_id = settings.BYTES_TTS_LONG_RESOURCE_ID.strip()
        query_resource_id = (
                settings.BYTES_TTS_LONG_QUERY_RESOURCE_ID.strip()
                or HuoshanLongTextTTSClient.infer_query_resource_id(resource_id)
        )
        return HuoshanLongTextTTSConfig(
            app_id=app_id,
            access_key=access_key,
            resource_id=resource_id,
            query_resource_id=query_resource_id,
            submit_url=settings.BYTES_TTS_LONG_SUBMIT_URL,
            query_url=settings.BYTES_TTS_LONG_QUERY_URL,
            timeout=settings.BYTES_TTS_LONG_TIMEOUT_SECONDS,
        )

    @classmethod
    def _create_openapi_client(cls) -> HuoshanOpenAPIClient:
        return HuoshanOpenAPIClient(cls._resolve_client_config())

    @classmethod
    def _create_story_client(cls, speaker: str | None = None) -> HuoshanLongTextTTSClient:
        return HuoshanLongTextTTSClient(cls._resolve_story_client_config(speaker))

    @staticmethod
    def _resolve_story_generation_model() -> str:
        return DEFAULT_DOUBAO_STORY_MODEL

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

    @staticmethod
    def _create_doubao_client() -> AsyncOpenAI:
        base_url = str(settings.DOUBAO_BASE_URL or '').strip()
        api_key = settings.DOUBAO_API_KEY.get_secret_value().strip()

        if not base_url:
            raise errors.ServerError(msg='DOUBAO_BASE_URL is not configured')
        if not api_key:
            raise errors.ServerError(msg='DOUBAO_API_KEY is not configured')

        return AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=httpx.AsyncClient(
                timeout=DOUBAO_HTTP_TIMEOUT,
                follow_redirects=True,
                limits=DOUBAO_HTTP_LIMITS,
            ),
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
                'text': obj.story_content,
                'speaker': obj.speaker,
                'audio_params': {
                    **STORY_AUDIO_PARAMS,
                    'speech_rate': int(obj.speech_rate),
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

    async def _get_voice_status(self, *, speaker: str) -> HuoshanVoiceStatus:
        project_name = await self._get_project_name(speaker)
        result = await self._list_voice_status_page(
            HuoshanVoiceListParam(project_name=project_name, speaker_ids=[speaker], state=None, page_size=10)
        )
        for status in result.statuses:
            if status.speaker_id == speaker:
                if status.state not in ('Success', 'Active'):
                    raise errors.RequestError(msg=f'Voice clone is not available, current state={status.state}')
                return self._attach_voice_remark(status)
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

    async def _list_voice_status_page(self, obj: HuoshanVoiceListParam) -> HuoshanVoiceListResult:
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

    async def list_all_voice_statuses(self, obj: HuoshanVoiceListParam) -> list[HuoshanVoiceStatus]:
        query = obj.model_copy(deep=True)
        if query.page_size is None:
            query.page_size = 100
        if query.page_number is None:
            query.page_number = 1
        if query.state is None:
            query.state = 'Success'

        result = await self._list_voice_status_page(query)
        return [self._attach_voice_remark(status) for status in result.statuses]

    async def order_voices(self, obj: HuoshanVoiceOrderParam) -> HuoshanVoiceOrderResponse:
        client = self._create_openapi_client()
        payload = obj.model_dump(exclude_none=True)

        try:
            data = await client.order_access_resource_packs(payload)
        except HuoshanOpenAPIError as exc:
            self._raise_api_error(exc)
            raise
        finally:
            await client.close()

        return HuoshanVoiceOrderResponse.model_validate(data)

    async def renew_voices(self, obj: HuoshanVoiceRenewParam) -> HuoshanVoiceRenewResponse:
        client = self._create_openapi_client()
        payload = obj.model_dump(exclude_none=True)

        try:
            data = await client.renew_access_resource_packs(payload)
        except HuoshanOpenAPIError as exc:
            self._raise_api_error(exc)
            raise
        finally:
            await client.close()

        return HuoshanVoiceRenewResponse.model_validate(data)

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
            client = self._create_doubao_client()
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
            model=self._resolve_story_generation_model(),
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
        mixed_audio = await self._mix_story_audio(
            speech_audio=speech_audio,
            bgm_play_url=current_result.bgm.play_url,
            bgm_volume=current_result.bgm_volume,
        )

        oss_key = self._build_story_oss_key(task_id=task_id)
        download_url = await self._upload_story_audio(key=oss_key, data=mixed_audio)
        if not download_url:
            raise errors.GatewayError(
                msg='Failed to upload mixed story audio to OSS',
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
            f'bgm_song_id={current_result.bgm.song_id}, oss_key={oss_key}'
        )
        return result

    async def _process_story_synthesis(self, task_id: str) -> HuoshanStorySynthesisResult:
        result = await self._get_story_synthesis_task_result(task_id)
        client = self._create_story_client(result.speaker)
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
            log.error(f'Huoshan story synthesis processing failed: task_id={task_id}, error={exc}')
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
        bgm_song = await self._get_bgm_song(db, obj.bgm_song_id)
        log.info(bgm_song)
        voice_status = await self._get_voice_status(speaker=obj.speaker)
        log.info(voice_status)
        story_client_config = self._resolve_story_client_config(obj.speaker)
        client = self._create_story_client(obj.speaker)

        try:
            submit_response = await client.submit(payload=self._build_story_payload(obj, uid=uuid.uuid4().hex))
        except HuoshanTTSError as exc:
            self._raise_api_error(exc)
            raise
        finally:
            await client.close()

        task_id = str((submit_response.get('data') or {}).get('task_id') or '').strip()
        if not task_id:
            raise errors.GatewayError(msg='Huoshan story synthesis did not return task_id', data=submit_response)

        result = HuoshanStorySynthesisResult(
            task_id=task_id,
            speaker=voice_status.speaker_id or '',
            speaker_alias=voice_status.speaker_alias,
            speaker_state=voice_status.state,
            resource_id=story_client_config.resource_id,
            audio_format=STORY_AUDIO_FORMAT,
            bgm=HuoshanStoryBgmInfo(
                song_id=bgm_song.id,
                title=bgm_song.title,
                play_url=str(bgm_song.play_url or '').strip(),
                artist=bgm_song.artist,
                duration=bgm_song.duration,
            ),
            bgm_volume=obj.bgm_volume,
            is_completed=False,
            task_status=STORY_TASK_STATUS_PROCESSING,
        )
        await self._save_story_synthesis_task_result(result)
        self._start_story_synthesis_processing(task_id)

        log.info(
            f'Huoshan story synthesis submitted: task_id={task_id}, speaker={obj.speaker}, '
            f'bgm_song_id={bgm_song.id}, resource_id={story_client_config.resource_id}'
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
