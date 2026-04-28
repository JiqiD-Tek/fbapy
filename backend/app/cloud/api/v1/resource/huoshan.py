# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : huoshan.py
@Author  : OpenAI
@Date    : 2026/04/13
"""

import struct
from typing import Annotated, AsyncGenerator

from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Path, Query

from backend.app.cloud.schema.resource.huoshan import (
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

from backend.app.cloud.service.resource.huoshan.asr.asr_stream import asr_stream_service
from backend.app.cloud.service.resource.huoshan.tts.tts_cache import tts_cache
from backend.app.cloud.service.resource.huoshan.tts.tts_stream import tts_stream_service
from backend.common.log import log

from backend.app.cloud.service.resource.huoshan.service import huoshan_voice_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSession

router = APIRouter()


@router.post(
    '/voices/all',
    summary='Query all Huoshan voice clone statuses as a flat list',
    # dependencies=[DependsJwtAuth],
    response_model_by_alias=False,
)
async def list_all_huoshan_voice_statuses(
        obj: HuoshanVoiceListParam,
) -> ResponseSchemaModel[list[HuoshanVoiceStatus]]:
    data = await huoshan_voice_service.list_all_voice_statuses(obj)
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


@router.post(
    '/tts/stream',
    summary='Submit simple Huoshan bidirectional TTS stream task',
    response_model_by_alias=False,
)
async def submit_huoshan_stream_tts(
        obj: HuoshanStreamTTSParam,
        # dependencies=[DependsJwtAuth],
) -> ResponseSchemaModel[HuoshanStreamTTSResult]:
    data = await tts_stream_service.submit(obj)
    return response_base.success(data=data)


@router.get("/tts", summary='获取tts语音', description='获取tts语音')
async def tts(
        token: Annotated[str, Query(description='TTS Token，格式为request_id')],
        type: Annotated[str, Query(description='音频格式，可选mp3或wav')] = "mp3",
        # dependencies=[DependsJwtAuth],
):
    """http TTS"""
    if not token:
        raise KeyError(f"Token格式错误")

    if type == "mp3":
        return await _generate_mp3_response(token)
    else:
        return await _generate_wav_response(token)


async def _generate_mp3_response(request_id: str) -> StreamingResponse:
    """生成MP3格式的音频响应"""

    async def audio_generator() -> AsyncGenerator[bytes, None]:
        try:
            async with tts_cache.stream_audio_generator(request_id) as stream:
                async for chunk in stream:
                    yield chunk
        except Exception as e:
            log.error(f"MP3音频流生成失败: {e}")
            raise

    return StreamingResponse(
        audio_generator(),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f'inline; filename="tts_{request_id}.mp3"',
            "X-Request-ID": request_id,
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )


async def _generate_wav_response(request_id: str) -> StreamingResponse:
    """生成WAV格式的音频响应"""

    def generate_wav_header(sample_rate: int = 24000, channels: int = 1, bit_depth: int = 16) -> bytes:
        """生成WAV文件头"""
        return struct.pack(
            '<4sI4s4sIHHIIHH4sI',
            b'RIFF', 0,  # 总大小稍后填充
            b'WAVE', b'fmt ',
            16,  # fmt块大小
            1,  # 音频格式（PCM）
            channels,
            sample_rate,
            sample_rate * channels * bit_depth // 8,
            channels * bit_depth // 8,
            bit_depth,
            b'data', 0  # 数据块大小稍后填充
        )

    async def audio_generator() -> AsyncGenerator[bytes, None]:
        """生成包含WAV头的音频流"""
        # 首先生成WAV头（占位符）
        wav_header = generate_wav_header(
            sample_rate=24000, channels=1, bit_depth=16
        )  # TODO 从配置中获取
        yield wav_header

        # 然后流式传输音频数据
        try:
            async with tts_cache.stream_audio_generator(request_id) as stream:
                async for chunk in stream:
                    yield chunk
        except Exception as e:
            log.error(f"WAV音频流生成失败: {e}")
            raise

    return StreamingResponse(
        audio_generator(),
        media_type="audio/wav",
        headers={
            "Content-Disposition": f'inline; filename="tts_{request_id}.wav"',
            "X-Request-ID": request_id,
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )
