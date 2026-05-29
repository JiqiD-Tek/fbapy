# -*- coding: UTF-8 -*-
"""
Huoshan resource API.
"""

from __future__ import annotations

import asyncio
import struct
from contextlib import suppress
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, Path, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from backend.app.cloud.schema.resource.huoshan import (
    HuoshanPublicVoiceInfo,
    HuoshanStreamASRParam,
    HuoshanStreamASRResult,
    HuoshanStreamTTSParam,
    HuoshanStreamTTSResult,
    HuoshanStoryGenerateParam,
    HuoshanStoryGenerateResult,
    HuoshanStorySynthesisParam,
    HuoshanStorySynthesisResult,
    HuoshanVoiceListParam,
    HuoshanVoiceOrderParam,
    HuoshanVoiceOrderResponse,
    HuoshanVoiceRenewParam,
    HuoshanVoiceRenewResponse,
    HuoshanVoiceStatus,
)
from backend.app.cloud.service.resource.huoshan.config import list_public_voices
from backend.app.cloud.service.resource.huoshan.asr.asr_stream import asr_stream_service
from backend.app.cloud.service.resource.huoshan.service import huoshan_voice_service
from backend.app.cloud.service.resource.huoshan.tts.tts_cache import tts_cache
from backend.app.cloud.service.resource.huoshan.tts.tts_stream import tts_stream_service
from backend.common.log import log
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSession

router = APIRouter()


@router.get(
    '/voices/public',
    summary='List Huoshan public voices',
    # dependencies=[DependsJwtAuth],
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
    summary='Query clone Huoshan voice clone statuses as a flat list',
    # dependencies=[DependsJwtAuth],
    response_model_by_alias=False,
)
async def list_clone_huoshan_voice_statuses(
        obj: HuoshanVoiceListParam,
) -> ResponseSchemaModel[list[HuoshanVoiceStatus]]:
    data = await huoshan_voice_service.list_clone_voice_statuses(obj)
    return response_base.success(data=data)


@router.post(
    '/voices/orders',
    summary='Create Huoshan voice clone orders',
    # dependencies=[DependsJwtAuth],
    response_model_by_alias=False,
)
async def order_huoshan_voices(
        obj: HuoshanVoiceOrderParam,
) -> ResponseSchemaModel[HuoshanVoiceOrderResponse]:
    data = await huoshan_voice_service.order_voices(obj)
    return response_base.success(data=data)


@router.post(
    '/voices/renewals',
    summary='Renew Huoshan voice clones',
    # dependencies=[DependsJwtAuth],
    response_model_by_alias=False,
)
async def renew_huoshan_voices(
        obj: HuoshanVoiceRenewParam,
) -> ResponseSchemaModel[HuoshanVoiceRenewResponse]:
    data = await huoshan_voice_service.renew_voices(obj)
    return response_base.success(data=data)


@router.post(
    '/stories/generate',
    summary='Generate a story by topic with Huoshan large model',
    # dependencies=[DependsJwtAuth],
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
    # dependencies=[DependsJwtAuth],
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
    # dependencies=[DependsJwtAuth],
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
    # dependencies=[DependsJwtAuth],
    response_model_by_alias=False,
)
async def get_huoshan_story_synthesis(
        task_id: str = Path(description='Huoshan task ID'),
) -> ResponseSchemaModel[HuoshanStorySynthesisResult]:
    data = await huoshan_voice_service.get_story_synthesis(task_id=task_id)
    return response_base.success(data=data)


@router.post(
    '/asr/stream',
    summary='Submit simple Huoshan stream ASR task',
    response_model_by_alias=False,
)
async def submit_huoshan_stream_asr(
        obj: HuoshanStreamASRParam,
        # dependencies=[DependsJwtAuth],
) -> ResponseSchemaModel[HuoshanStreamASRResult]:
    data = await asr_stream_service.transcribe(obj)
    return response_base.success(data=data)


@router.websocket('/asr/stream/ws')
async def websocket_huoshan_stream_asr(
        websocket: WebSocket,
        sample_rate: Annotated[int, Query(gt=0)] = 16000,
        bits: Annotated[int, Query(gt=0)] = 16,
        channel: Annotated[int, Query(gt=0)] = 1,
) -> None:
    await websocket.accept()
    session = None
    forward_task = None

    try:
        session = await asr_stream_service.create_realtime_session(
            sample_rate=sample_rate,
            bits=bits,
            channel=channel,
        )
        forward_task = asyncio.create_task(
            _forward_huoshan_asr_ws_events(websocket, session),
            name=f'huoshan-asr-ws:{session.request_id}',
        )

        if await _receive_huoshan_asr_ws_audio(websocket, session):
            with suppress(Exception):
                await forward_task
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.error(f'Huoshan ASR realtime websocket failed: {exc!r}')
    finally:
        if forward_task is not None and not forward_task.done():
            forward_task.cancel()
            with suppress(asyncio.CancelledError):
                await forward_task
        if session is not None:
            await session.close()
        with suppress(Exception):
            await websocket.close()


async def _receive_huoshan_asr_ws_audio(
        websocket: WebSocket,
        session,
) -> bool | None:
    while True:
        message = await websocket.receive()
        if message['type'] == 'websocket.disconnect':
            return False

        audio_chunk = message.get('bytes')
        if audio_chunk is None:
            continue
        if not audio_chunk:
            await session.finish_input()
            return True

        await session.send_audio_chunk(audio_chunk)


async def _forward_huoshan_asr_ws_events(
        websocket: WebSocket,
        session,
) -> None:
    try:
        async for event in session.iter_events():
            await websocket.send_json(event)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.error(
            f'Huoshan ASR realtime forward failed: request_id={session.request_id}, error={exc!r}'
        )
    finally:
        with suppress(Exception):
            await websocket.close()


@router.post(
    '/tts/stream',
    summary='Submit simple Huoshan bidirectional TTS stream task',
    # dependencies=[DependsJwtAuth],
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
            async with tts_cache.stream_audio_generator(request_id) as stream:
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
            async with tts_cache.stream_audio_generator(request_id) as stream:
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
