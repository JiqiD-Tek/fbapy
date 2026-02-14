# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：tts.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/15 16:35
"""

import asyncio
import gzip
import json
import traceback
import uuid

from collections.abc import Callable
from typing import Any, Optional

from pydantic import BaseModel
from websockets import ConnectionClosedError, ConnectionClosedOK

from backend.app.live.agents.core.tts.tts import TTS
from backend.app.live.agents.core.utils import aio
from backend.app.live.agents.providers.coze.ws import AsyncWebSocketClient
from backend.common.log import log
from backend.core.conf import settings

MESSAGE_TYPES = {11: 'audio-only server response', 12: 'frontend server response', 15: 'error message from server'}
MESSAGE_TYPE_SPECIFIC_FLAGS = {
    0: 'no sequence number',
    1: 'sequence number > 0',
    2: 'last message from server (seq < 0)',
    3: 'sequence number < 0',
}
MESSAGE_SERIALIZATION_METHODS = {0: 'no serialization', 1: 'JSON', 15: 'custom type'}
MESSAGE_COMPRESSIONS = {0: 'no compression', 1: 'gzip', 15: 'custom compression method'}


class AppConfig(BaseModel):
    """应用配置"""

    appid: str
    token: str
    cluster: str


class UserConfig(BaseModel):
    """用户配置"""

    uid: str


class AudioConfig(BaseModel):
    """音频参数配置"""

    voice_type: str  # 音色类型
    encoding: str = 'wav'  # 音频编码格式， wav / pcm / ogg_opus / mp3，默认为 pcm 注意：wav 不支持流式
    speed_ratio: float = 1.0  # 语速 [0.2,3]，默认为1，通常保留一位小数即可
    volume_ratio: float = 1.0  # 音量 [0.1, 3]，默认为1，通常保留一位小数即可
    pitch_ratio: float = 1.0  # 音高 [0.1, 3]，默认为1，通常保留一位小数即可


class RequestConfig(BaseModel):
    """请求参数配置"""

    reqid: str  # 需要保证每次调用传入值唯一，建议使用 UUID
    text: str  # 合成语音的文本，长度限制 1024 字节（UTF-8编码）。复刻音色没有此限制，但是HTTP接口有60s超时限制
    text_type: str  # 文本类型 plain / ssml, 默认为plain
    operation: str  # 操作 query（非流式，http只能query） / submit（流式）


class TTSConfig(BaseModel):
    """语音合成请求总配置"""

    app: AppConfig
    user: UserConfig
    audio: AudioConfig
    request: RequestConfig

    def to_json(self) -> dict:
        return self.model_dump(by_alias=True)  # 自动处理别名


def create_tts_config(
        appid: str,
        token: str,
        cluster: str,
        uid: str = '',
        text: str = '',
        reqid: str = '',
        text_type: str = 'plain',
        operation: str = 'submit',
        voice_type: str = 'BV064_streaming',  # https://www.volcengine.com/docs/6561/97465  S_HFruD8as1 BV064_streaming
        encoding: str = 'pcm',
        speed_ratio: float = 1.0,
        volume_ratio: float = 1.0,
        pitch_ratio: float = 1.0,
) -> TTSConfig:
    """
    创建TTS（文本转语音）请求对象的工厂方法

    Args:
        text (str): 需要合成的文本内容，支持普通文本或SSML格式
        appid (str): 应用唯一标识，从控制台获取
        cluster (str): 服务集群名称，如"default"、"pre-prod"等
        token (str): 接口认证token，有效期通常为24小时
        uid (str): 用户唯一标识，用于区分不同用户请求
        reqid (str): 请求唯一标识，用于问题追踪（建议使用UUID）
        text_type (str, optional): 文本类型，可选"plain"（普通文本）或"ssml"。默认为"plain"
        operation (str, optional): 操作类型，如"submit"（提交合成）、"query"（查询状态）。默认为"submit"
        voice_type (str, optional): 音色类型，如"BV001_streaming"（流式女声）。默认为"BV001_streaming"
        encoding (str, optional): 音频编码格式，如"mp3"、"pcm"。默认为"mp3"
        speed_ratio (float, optional): 语速比例（0.5-2.0），1.0为正常语速。默认为1.0
        volume_ratio (float, optional): 音量比例（0.0-2.0），1.0为正常音量。默认为1.0
        pitch_ratio (float, optional): 音高比例（0.5-1.5），1.0为正常音高。默认为1.0
    Returns:
        TTSConfig: 配置完成的TTS请求对象

    """
    config = TTSConfig(
        app=AppConfig(
            appid=appid,
            token=token,
            cluster=cluster,
        ),
        user=UserConfig(
            uid=uid,
        ),
        audio=AudioConfig(
            voice_type=voice_type,
            encoding=encoding,
            speed_ratio=speed_ratio,
            volume_ratio=volume_ratio,
            pitch_ratio=pitch_ratio,
        ),
        request=RequestConfig(
            reqid=reqid,
            text=text,
            operation=operation,
            text_type=text_type,
        ),
    )
    return config


def get_tts_config(icl=settings.BYTES_ICL_STATUS, encoding: str = 'wav', language: str = 'zh-CN'):
    return create_tts_config(
        appid=settings.BYTES_TTS_APPID,
        token=settings.BYTES_TTS_TOKEN,
        encoding='pcm' if encoding == 'wav' else 'mp3',
        cluster=settings.BYTES_ICL_CLUSTER if icl else settings.BYTES_TTS_CLUSTER,
        voice_type=settings.BYTES_ICL_VOICE_TYPE if icl else settings.BYTES_TTS_VOICE_TYPE,
        uid=uuid.uuid4().hex,
    )


class CozeTTS(AsyncWebSocketClient, TTS):
    """优化的TTS合成客户端（支持WebSocket流式传输）"""

    def __init__(self, url: str = settings.BYTES_TTS_URL, language: str = 'zh-CN') -> None:
        """初始化TTS客户端"""
        self.tts_config = get_tts_config(language=language)
        super().__init__(url=url, token=self.tts_config.app.token, language=language)

        self._task = asyncio.create_task(self._run())  # 启动事件循环

    async def _run(self) -> None:
        """事件循环"""

        async def _input_task() -> None:
            async for data in self._input_ch:
                if isinstance(data, self._FlushSentinel):
                    self._tokenizer_stream.flush()
                    continue
                self._tokenizer_stream.push_text(data)

            self._tokenizer_stream.end_input()

        async def _recv_task() -> None:
            async for ev in self._tokenizer_stream:
                try:
                    await self._handle_request(ev.token)
                except Exception as e:
                    log.error(f'TTS合成异常: {e}')

                if self._tokenizer_stream._current_segment_id != ev.segment_id:
                    log.debug(f'TTS合成结束: {ev}')
                    await self._audio_callback(b'')  # 发送空数据表示结束

        tasks = [
            asyncio.create_task(_input_task()),
            asyncio.create_task(_recv_task()),
        ]

        await asyncio.gather(*tasks)

    def push_text(self, token: str) -> None:
        self._input_ch.send_nowait(token)

    def set_callback(self, callback: Optional[Callable] = None) -> None:
        self._audio_callback = callback

    async def aclose(self, code: int = 1000, reason: str = '') -> None:
        """安全关闭TTS客户端并释放所有资源"""
        try:
            await super().aclose(reason='TTS 关闭')
            await aio.cancel_and_wait(self._task)
            await self.tts_cache.aclose()
        except Exception as e:
            log.error(f'关闭TTS处理器时发生异常: {e}', exc_info=True)

    async def _handle_request(self, token: str) -> None:
        request = self._prepare_request(text=token)

        await self.ensure_connection()
        await self._conn.send(request)

        while True:
            try:
                resp = await asyncio.wait_for(self._conn.recv(), timeout=10.0)
                if self._audio_callback is None:
                    continue

                done = await self._parse_response(resp, self._audio_callback)
                if done:
                    break

            except asyncio.TimeoutError:
                log.warning('TTS响应超时，可能服务端无数据')
                break
            except ConnectionClosedOK:
                log.info('TTS WebSocket 正常关闭（1000），合成完成')
                break
            except ConnectionClosedError as e:
                log.error(f'TTS WebSocket 异常关闭: {e}')
                raise
            except Exception as e:
                log.error(f'TTS处理器发生未捕获异常 - {e} - {traceback.format_exc()}')
                raise

    def _prepare_request(self, text: str, operation: str = 'query') -> bytearray:
        """
        Prepare the request payload with optional operation type
        """
        # Generate new request ID
        self.tts_config.request.reqid = uuid.uuid4().hex
        self.tts_config.request.text = text
        # Set operation
        self.tts_config.request.operation = operation
        # Serialize and compress the request
        payload_bytes = str.encode(json.dumps(self.tts_config.model_dump()))
        payload_bytes = gzip.compress(payload_bytes)  # if no compression, comment this line
        # Build the full request
        request = bytearray(b'\x11\x10\x11\x00')
        request.extend(len(payload_bytes).to_bytes(4, 'big'))  # Big-endian payload size
        request.extend(payload_bytes)
        return request

    @staticmethod
    async def _parse_response(resp: bytes, audio_callback: Callable[[bytes], Any]):
        protocol_version = resp[0] >> 4
        header_size = resp[0] & 0x0F
        message_type = resp[1] >> 4
        message_type_specific_flags = resp[1] & 0x0F
        serialization_method = resp[2] >> 4
        message_compression = resp[2] & 0x0F
        reserved = resp[3]
        header_extensions = resp[4: header_size * 4]
        payload = resp[header_size * 4:]

        log.debug(f'Protocol version: {protocol_version:#x} - version {protocol_version}')
        log.debug(f'Header size: {header_size:#x} - {header_size * 4} bytes')
        log.debug(f'Message type: {message_type:#x} - {MESSAGE_TYPES[message_type]}')
        log.debug(
            f'Message type specific flags: {message_type_specific_flags:#x} - {MESSAGE_TYPE_SPECIFIC_FLAGS[message_type_specific_flags]}'
        )
        log.debug(
            f'Message serialization method: {serialization_method:#x} - {MESSAGE_SERIALIZATION_METHODS[serialization_method]}'
        )
        log.debug(f'Message compression: {message_compression:#x} - {MESSAGE_COMPRESSIONS[message_compression]}')
        log.debug(f'Reserved: {reserved:#04x}')

        if header_size != 1:
            log.debug(f'Header extensions: {header_extensions}')

        if message_type == 0xB:  # audio-only server response
            if message_type_specific_flags == 0:  # no sequence number as ACK
                return False
            sequence_number = int.from_bytes(payload[:4], 'big', signed=True)
            payload_size = int.from_bytes(payload[4:8], 'big', signed=False)
            payload = payload[8:]
            log.debug(f'Sequence number: {sequence_number}')
            log.debug(f'Payload size: {payload_size} bytes')

            await audio_callback(payload)  # 音频合成回调函数

            return sequence_number < 0

        if message_type == 0xF:
            code = int.from_bytes(payload[:4], 'big', signed=False)
            msg_size = int.from_bytes(payload[4:8], 'big', signed=False)
            error_msg = payload[8:]
            if message_compression == 1:
                error_msg = gzip.decompress(error_msg)
            error_msg = str(error_msg, 'utf-8')
            log.error(f'Error message code: {code}')
            log.error(f'Error message size: {msg_size} bytes')
            log.error(f'Error message: {error_msg}')
            return True

        if message_type == 0xC:
            msg_size = int.from_bytes(payload[:4], 'big', signed=False)
            payload = payload[4:]
            if message_compression == 1:
                payload = gzip.decompress(payload)

            log.debug(f'Frontend message: {payload} - {msg_size}')
            return None

        log.debug('undefined message type!')
        return True
