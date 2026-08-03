# -*- coding: UTF-8 -*-
"""
Huoshan resource API.
"""

from __future__ import annotations

import struct
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import StreamingResponse

from backend.app.cloud.schema.resource.huoshan import (
    HuoshanPublicVoiceInfo,
    HuoshanStreamTTSParam,
    HuoshanStreamTTSResult,
    HuoshanStoryGenerateParam,
    HuoshanStoryGenerateResult,
    HuoshanStorySynthesisParam,
    HuoshanStorySynthesisResult,
    HuoshanToyStoryScriptParam,
    HuoshanToyStoryScriptResult,
    HuoshanVoiceListParam,
    HuoshanVoiceStatus,
)
from backend.app.cloud.service.resource.huoshan.config import list_public_voices
from backend.app.cloud.service.resource.huoshan.service import huoshan_voice_service
from backend.app.cloud.service.resource.huoshan.tts.tts_cache import tts_cache
from backend.app.cloud.service.resource.huoshan.tts.tts_stream import tts_stream_service
from backend.common.log import log
from backend.common.response.response_schema import ResponseSchemaModel, response_base, ResponseModel
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.get(
    '/voices/public',
    summary='List Huoshan public voices',
    response_model_by_alias=False,
)
async def list_huoshan_public_voices() -> ResponseSchemaModel[list[HuoshanPublicVoiceInfo]]:
    data = [
        HuoshanPublicVoiceInfo(
            speaker=voice.id,
            name=voice.name,
            resource_id=str(voice.resource_id or '').strip(),
        )
        for voice in list_public_voices()
    ]
    return response_base.success(data=data)


@router.post(
    '/voices/clone',
    summary='List Huoshan clone voices',
    response_model_by_alias=False,
)
async def list_clone_huoshan_voice_statuses(
        obj: HuoshanVoiceListParam,
) -> ResponseSchemaModel[list[HuoshanVoiceStatus]]:
    data = await huoshan_voice_service.list_clone_voice_statuses(obj)
    return response_base.success(data=data)


@router.post(
    '/stories/script',
    summary='Submit toy-based story script generation task',
    response_model_by_alias=False,
    dependencies=[DependsJwtAuth],
)
async def submit_huoshan_toy_story_script(
        db: CurrentSession,
        obj: HuoshanToyStoryScriptParam,
) -> ResponseSchemaModel[HuoshanToyStoryScriptResult]:
    data = await huoshan_voice_service.submit_toy_story_script(db=db, obj=obj)
    return response_base.success(data=data)


@router.get(
    '/stories/script',
    summary='Query toy-based story script generation task status',
    response_model_by_alias=False,
    dependencies=[DependsJwtAuth],
)
async def get_huoshan_toy_story_script(
        task_id: Annotated[str, Query(description='Story script generation task ID')],
) -> ResponseSchemaModel[HuoshanToyStoryScriptResult]:
    data = await huoshan_voice_service.get_toy_story_script(task_id=task_id)
    return response_base.success(data=data)


@router.get(
    '/stories/script/tts',
    summary='Query toy-based story script generation task tts',
    response_model_by_alias=False,
    dependencies=[DependsJwtAuth],
)
async def get_huoshan_toy_story_tts(
        task_id: Annotated[str, Query(description='Story script generation task ID')],
        token: Annotated[str, Query(description='TTS token, usually request_id')],
):
    await huoshan_voice_service.submit_tts_task(task_id=task_id, token=token)
    return await _generate_mp3_response(token)


@router.post(
    '/stories/generate',
    summary='Generate a story by topic with Huoshan large model',
    response_model_by_alias=False,
)
async def generate_huoshan_story(
        obj: HuoshanStoryGenerateParam,
) -> ResponseSchemaModel[HuoshanStoryGenerateResult]:
    data = await huoshan_voice_service.submit_story_generation(obj)
    return response_base.success(data=data)


@router.get(
    '/stories/generate/{task_id}',
    summary='Query Huoshan story generation task status',
    response_model_by_alias=False,
)
async def get_huoshan_story_generation(
        task_id: str = Path(description='Story generation task ID'),
) -> ResponseSchemaModel[HuoshanStoryGenerateResult]:
    data = await huoshan_voice_service.get_story_generation(task_id=task_id)
    return response_base.success(data=data)


@router.post(
    '/stories/synthesis',
    summary='Submit Huoshan story synthesis task',
    response_model_by_alias=False,
)
async def synthesize_huoshan_story(
        db: CurrentSession,
        obj: HuoshanStorySynthesisParam,
) -> ResponseSchemaModel[HuoshanStorySynthesisResult]:
    data = await huoshan_voice_service.synthesize_story(db=db, obj=obj)
    return response_base.success(data=data)


@router.get(
    '/stories/synthesis/{task_id}',
    summary='Query Huoshan story synthesis task status',
    response_model_by_alias=False,
)
async def get_huoshan_story_synthesis(
        task_id: str = Path(description='Huoshan task ID'),
) -> ResponseSchemaModel[HuoshanStorySynthesisResult]:
    data = await huoshan_voice_service.get_story_synthesis(task_id=task_id)
    return response_base.success(data=data)


@router.post(
    '/tts/stream',
    summary='Submit simple Huoshan bidirectional TTS stream task',
    response_model_by_alias=False,
)
async def submit_huoshan_stream_tts(
        obj: HuoshanStreamTTSParam,
) -> ResponseSchemaModel[HuoshanStreamTTSResult]:
    data = await tts_stream_service.submit(obj)
    return response_base.success(data=data)


@router.get('/tts', summary='Get TTS audio', description='Get TTS audio')
async def tts(
        token: Annotated[str, Query(description='TTS token, usually request_id')],
        type: Annotated[str, Query(description='Audio format, mp3 or wav')] = 'mp3',
):
    if not token:
        raise KeyError('Invalid TTS token')

    if type == 'mp3':
        return await _generate_mp3_response(token)
    return await _generate_wav_response(token)


async def _generate_mp3_response(request_id: str) -> StreamingResponse:
    async def audio_generator() -> AsyncGenerator[bytes, None]:
        try:
            async with tts_cache.stream_audio_generator(request_id=request_id) as stream:
                async for chunk in stream:
                    yield chunk
        except Exception as exc:
            log.error(f'Failed to stream MP3 audio: {exc}')
            raise

    return StreamingResponse(
        audio_generator(),
        media_type='audio/mpeg',
        headers={
            'Content-Disposition': f'inline; filename="tts_{request_id}.mp3"',
            'X-Request-ID': request_id,
            'Cache-Control': 'no-store, no-cache, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
        },
    )


async def _generate_wav_response(request_id: str) -> StreamingResponse:
    def generate_wav_header(
            sample_rate: int = 24000,
            channels: int = 1,
            bit_depth: int = 16,
    ) -> bytes:
        byte_rate = sample_rate * channels * bit_depth // 8
        block_align = channels * bit_depth // 8
        return struct.pack(
            '<4sI4s4sIHHIIHH4sI',
            b'RIFF',
            0,
            b'WAVE',
            b'fmt ',
            16,
            1,
            channels,
            sample_rate,
            byte_rate,
            block_align,
            bit_depth,
            b'data',
            0,
        )

    async def audio_generator() -> AsyncGenerator[bytes, None]:
        yield generate_wav_header(sample_rate=24000, channels=1, bit_depth=16)

        try:
            async with tts_cache.stream_audio_generator(request_id=request_id) as stream:
                async for chunk in stream:
                    yield chunk
        except Exception as exc:
            log.error(f'Failed to stream WAV audio: {exc}')
            raise

    return StreamingResponse(
        audio_generator(),
        media_type='audio/wav',
        headers={
            'Content-Disposition': f'inline; filename="tts_{request_id}.wav"',
            'X-Request-ID': request_id,
            'Cache-Control': 'no-store, no-cache, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
        },
    )
