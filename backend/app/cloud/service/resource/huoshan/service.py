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

from backend.app.cloud.schema.huoshan import (
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
from backend.common.ali_oss import oss_client
from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.database.redis import redis_client
from backend.utils.timezone import timezone

from .audio_tools import mix_audio_with_bgm
from .client import HuoshanLongTextTTSClient, HuoshanOpenAPIClient
from .exceptions import HuoshanAPIError, HuoshanOpenAPIError, HuoshanTTSError
from .models import HuoshanLongTextTTSConfig, HuoshanOpenAPIConfig

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
HUOSHAN_VOICE_REMARK_MAP = {
    'S_GKcK2x2X1': '曲老师',
    'S_EKcK2x2X1': '虾球',
    'S_DKcK2x2X1': '米粒',
    'S_CKcK2x2X1': '旁白',
    'S_BKcK2x2X1': '珍棒',
    'S_AKcK2x2X1': '珍居',
    'S_zKcK2x2X1': '未上传数据',
    'S_yKcK2x2X1': '未上传数据',
}


class HuoshanVoiceService:
    STORY_TASK_CACHE_PREFIX = 'fba:huoshan:story'

    def __init__(self) -> None:
        self._story_processing_tasks: dict[str, asyncio.Task[HuoshanStorySynthesisResult]] = {}

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
    def _resolve_story_client_config() -> HuoshanLongTextTTSConfig:
        resource_id = settings.BYTES_TTS_LONG_RESOURCE_ID.strip()
        query_resource_id = (
                settings.BYTES_TTS_LONG_QUERY_RESOURCE_ID.strip()
                or HuoshanLongTextTTSClient.infer_query_resource_id(resource_id)
        )
        return HuoshanLongTextTTSConfig(
            app_id=settings.BYTES_TTS_APPID.strip(),
            access_key=settings.BYTES_TTS_TOKEN.strip(),
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
    def _create_story_client(cls) -> HuoshanLongTextTTSClient:
        return HuoshanLongTextTTSClient(cls._resolve_story_client_config())

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
                'audio_params': dict(STORY_AUDIO_PARAMS),
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
    def _story_task_key(cls, task_id: str) -> str:
        return f'{cls.STORY_TASK_CACHE_PREFIX}:{task_id}'

    @staticmethod
    def _story_task_ttl_seconds() -> int:
        return max(int(settings.CACHE_REDIS_TTL), int(settings.BYTES_TTS_LONG_QUERY_TIMEOUT_SECONDS))

    @classmethod
    async def _save_story_task_result(cls, result: HuoshanStorySynthesisResult) -> None:
        try:
            await redis_client.set(
                cls._story_task_key(result.task_id),
                result.model_dump_json(),
                ex=cls._story_task_ttl_seconds(),
            )
        except Exception as exc:
            raise errors.GatewayError(msg='Failed to save Huoshan story task result') from exc

    @classmethod
    async def _get_story_task_result(cls, task_id: str) -> HuoshanStorySynthesisResult:
        try:
            payload_raw = await redis_client.get(cls._story_task_key(task_id))
        except Exception as exc:
            raise errors.GatewayError(msg='Failed to load Huoshan story task result') from exc

        if not payload_raw:
            raise errors.NotFoundError(msg=f'Huoshan story task not found, task_id={task_id}')
        return HuoshanStorySynthesisResult.model_validate_json(payload_raw)

    def _start_story_synthesis_processing(self, task_id: str) -> None:
        current_task = self._story_processing_tasks.get(task_id)
        if current_task is not None and not current_task.done():
            return

        task = asyncio.create_task(
            self._process_story_synthesis(task_id),
            name=f'huoshan-story-synthesis-{task_id}',
        )
        self._story_processing_tasks[task_id] = task

        def _cleanup(done_task: asyncio.Task[HuoshanStorySynthesisResult]) -> None:
            if self._story_processing_tasks.get(task_id) is done_task:
                self._story_processing_tasks.pop(task_id, None)

        task.add_done_callback(_cleanup)

    async def _get_voice_status(self, *, speaker: str) -> HuoshanVoiceStatus:
        result = await self._list_voice_status_page(
            HuoshanVoiceListParam(speaker_ids=[speaker], state=None, page_size=10)
        )
        for status in result.statuses:
            if status.speaker_id == speaker:
                if status.state not in ('Success', 'Active'):
                    raise errors.RequestError(msg=f'Voice clone is not available, current state={status.state}')
                return self._attach_voice_remark(status)
        raise errors.NotFoundError(msg='Voice clone does not exist')

    @classmethod
    async def _mix_story_audio(cls, *, speech_audio: bytes, bgm_play_url: str) -> bytes:
        with TemporaryDirectory(prefix='huoshan_story_') as temp_dir:
            speech_path = Path(temp_dir) / f'speech.{STORY_AUDIO_FORMAT}'
            output_path = Path(temp_dir) / f'mixed.{STORY_AUDIO_FORMAT}'

            speech_path.write_bytes(speech_audio)
            await asyncio.to_thread(mix_audio_with_bgm, speech_path, bgm_play_url, output_path)
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
        result = await self._get_story_task_result(task_id)
        client = self._create_story_client()
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
                await self._save_story_task_result(result)

                if provider_task_status == 2:
                    result = await self._finalize_story_synthesis(
                        current_result=result,
                        client=client,
                    )
                    await self._save_story_task_result(result)
                    return result

                if provider_task_status == 3:
                    result = result.model_copy(update={
                        'task_status': STORY_TASK_STATUS_FAILED,
                        'error_message': 'Huoshan story synthesis task failed',
                    }, deep=True)
                    await self._save_story_task_result(result)
                    return result

                if monotonic() >= deadline:
                    result = result.model_copy(update={
                        'task_status': STORY_TASK_STATUS_FAILED,
                        'error_message': f'Huoshan story synthesis task timed out, task_id={task_id}',
                    }, deep=True)
                    await self._save_story_task_result(result)
                    return result

                await asyncio.sleep(settings.BYTES_TTS_LONG_QUERY_INTERVAL_SECONDS)
        except HuoshanTTSError as exc:
            log.error(f'Huoshan story synthesis processing failed: task_id={task_id}, error={exc}')
            result = result.model_copy(update={
                'task_status': STORY_TASK_STATUS_FAILED,
                'error_message': exc.message,
            }, deep=True)
            await self._save_story_task_result(result)
            return result
        except Exception as exc:
            log.error(f'Huoshan story synthesis processing failed: task_id={task_id}, error={exc!r}')
            result = result.model_copy(update={
                'task_status': STORY_TASK_STATUS_FAILED,
                'error_message': str(exc),
            }, deep=True)
            await self._save_story_task_result(result)
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
        voice_status = await self._get_voice_status(speaker=obj.speaker)
        story_client_config = self._resolve_story_client_config()
        client = self._create_story_client()

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
            is_completed=False,
            task_status=STORY_TASK_STATUS_PROCESSING,
        )
        await self._save_story_task_result(result)
        self._start_story_synthesis_processing(task_id)

        log.info(
            f'Huoshan story synthesis submitted: task_id={task_id}, speaker={obj.speaker}, '
            f'bgm_song_id={bgm_song.id}, resource_id={story_client_config.resource_id}'
        )

        return result

    async def get_story_synthesis(self, *, task_id: str) -> HuoshanStorySynthesisResult:
        return await self._get_story_task_result(task_id)


huoshan_voice_service = HuoshanVoiceService()
