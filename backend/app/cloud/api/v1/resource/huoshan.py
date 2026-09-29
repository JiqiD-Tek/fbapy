# -*- coding: UTF-8 -*-
"""火山相关资源接口。"""

from __future__ import annotations

import struct
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import StreamingResponse

from backend.app.cloud.schema.resource.huoshan import (
    HuoshanPublicVoiceInfo,
    HuoshanStreamTTSParam,
    HuoshanStreamTTSResult,
    HuoshanStorySynthesisParam,
    HuoshanStorySynthesisResult,
    HuoshanToyStoryScriptParam,
    HuoshanToyStoryScriptResult,
    HuoshanVoiceListParam,
    HuoshanVoiceStatus,
)
from backend.app.cloud.schema.user import DeviceAuthParam
from backend.app.cloud.service.resource.huoshan.config import list_public_voices
from backend.app.cloud.service.resource.huoshan.service import huoshan_voice_service
from backend.app.cloud.service.resource.huoshan.tts.tts_cache import tts_cache
from backend.app.cloud.service.resource.huoshan.tts.tts_stream import tts_stream_service
from backend.common.log import log
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.auth import DependsDeviceOrJwtAuth
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSessionTransaction, CurrentSession

router = APIRouter()


@router.get(
    '/voices/public',
    summary='获取火山公共声音列表',
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
    summary='获取火山克隆声音列表',
    response_model_by_alias=False,
)
async def list_clone_huoshan_voice_statuses(
        obj: HuoshanVoiceListParam,
) -> ResponseSchemaModel[list[HuoshanVoiceStatus]]:
    data = await huoshan_voice_service.list_clone_voice_statuses(obj)
    return response_base.success(data=data)


# 玩偶剧本
@router.post(
    '/stories/script',
    summary='提交玩偶故事剧本生成任务',
    response_model_by_alias=False,
)
async def submit_huoshan_toy_story_script(
        db: CurrentSessionTransaction,
        obj: HuoshanToyStoryScriptParam,
        auth_ctx: object = DependsDeviceOrJwtAuth,
) -> ResponseSchemaModel[HuoshanToyStoryScriptResult]:
    device_did = auth_ctx.did if isinstance(auth_ctx, DeviceAuthParam) else None
    data = await huoshan_voice_service.submit_toy_story_script(db=db, obj=obj, device_did=device_did)
    return response_base.success(data=data)


@router.get(
    '/stories/script',
    summary='查询玩偶故事剧本生成任务状态',
    response_model_by_alias=False,
    dependencies=[DependsJwtAuth],
)
async def get_huoshan_toy_story_script(
        task_id: Annotated[str, Query(description='故事剧本生成任务 ID')],
) -> ResponseSchemaModel[HuoshanToyStoryScriptResult]:
    data = await huoshan_voice_service.get_toy_story_script(task_id=task_id)
    return response_base.success(data=data)


# TTS 合成
@router.get(
    '/stories/script/tts',
    summary='获取玩偶故事剧本语音',
    response_model_by_alias=False,
    dependencies=[DependsJwtAuth],
)
async def get_huoshan_toy_story_tts(
        task_id: Annotated[str, Query(description='故事剧本生成任务 ID')],
        token: Annotated[str, Query(description='语音合成令牌，通常为 request_id')],
):
    await huoshan_voice_service.submit_tts_task(task_id=task_id, token=token)
    return await _generate_mp3_response(token)


@router.post(
    '/stories/synthesis',
    summary='提交火山故事合成任务',
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
    summary='查询火山故事合成任务状态',
    response_model_by_alias=False,
)
async def get_huoshan_story_synthesis(
        task_id: str = Path(description='火山任务 ID'),
) -> ResponseSchemaModel[HuoshanStorySynthesisResult]:
    data = await huoshan_voice_service.get_story_synthesis(task_id=task_id)
    return response_base.success(data=data)


@router.post(
    '/tts/stream',
    summary='提交火山双向语音合成流任务',
    response_model_by_alias=False,
)
async def submit_huoshan_stream_tts(
        obj: HuoshanStreamTTSParam,
) -> ResponseSchemaModel[HuoshanStreamTTSResult]:
    data = await tts_stream_service.submit(obj)
    return response_base.success(data=data)


@router.get('/tts', summary='获取语音合成音频', description='获取语音合成音频')
async def tts(
        token: Annotated[str, Query(description='语音合成令牌，通常为 request_id')],
        type: Annotated[str, Query(description='音频格式，支持 mp3 或 wav')] = 'mp3',
):
    if not token:
        raise KeyError('语音合成令牌不能为空')

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
            log.error(f'MP3 音频流输出失败：{exc}')
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
            log.error(f'WAV 音频流输出失败：{exc}')
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
