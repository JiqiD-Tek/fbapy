#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author    : guhua@jiqid.com
# @File      : protocol.py
# @Created   : 2025/4/11 17:23

import struct
from typing import Annotated, AsyncGenerator

from fastapi import WebSocket, APIRouter, Query
from fastapi.responses import StreamingResponse

from backend.common.log import log
from backend.common.wscore.gateway import connection_gateway

from backend.app.vce.service.coze.chat.chat_service import chat_service
from backend.core.conf import settings

router = APIRouter()


@router.websocket("")
async def chat(
        websocket: WebSocket,
):
    """CHAT"""
    await chat_service.receive_loop(websocket)


@router.get("/tts", summary='获取tts语音', description='获取tts语音')
async def tts(
        token: Annotated[str, Query(description='TTS Token，格式为uid.request_id')],
):
    """http TTS"""
    if "." not in token:
        raise KeyError(f"Token格式错误，应为uid.request_id")

    uid, request_id = token.rsplit('.', maxsplit=1)
    conn = await connection_gateway.get_connection(uid)

    if conn is None or conn.tts_client is None:
        raise KeyError(f"TTS client not exist")

    if settings.SPEECH_ENCODING == "mp3":
        return await _generate_mp3_response(conn, request_id)
    else:
        return await _generate_wav_response(conn, request_id)


async def _generate_mp3_response(conn, request_id: str) -> StreamingResponse:
    """生成MP3格式的音频响应"""

    async def audio_generator() -> AsyncGenerator[bytes, None]:
        try:
            async with conn.tts_client.tts_cache.stream_audio_generator(request_id) as stream:
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


async def _generate_wav_response(conn, request_id: str) -> StreamingResponse:
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
            async with conn.tts_client.tts_cache.stream_audio_generator(request_id) as stream:
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
