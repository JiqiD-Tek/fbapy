# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：asr_client.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/15 16:35
"""
import uuid
import gzip
import json

import asyncio
import traceback

from dataclasses import field, dataclass
from typing import Callable, Any, Deque, Optional
from collections import deque
from pydantic import BaseModel

from backend.common.log import log
from backend.common.openai.speech.base.asr import ASR
from backend.common.openai.speech.base.ws import AsyncWebSocketClient

PROTOCOL_VERSION = 0b0001
DEFAULT_HEADER_SIZE = 0b0001

PROTOCOL_VERSION_BITS = 4
HEADER_BITS = 4
MESSAGE_TYPE_BITS = 4
MESSAGE_TYPE_SPECIFIC_FLAGS_BITS = 4
MESSAGE_SERIALIZATION_BITS = 4
MESSAGE_COMPRESSION_BITS = 4
RESERVED_BITS = 8

# Message Type:
CLIENT_FULL_REQUEST = 0b0001
CLIENT_AUDIO_ONLY_REQUEST = 0b0010
SERVER_FULL_RESPONSE = 0b1001
SERVER_ACK = 0b1011
SERVER_ERROR_RESPONSE = 0b1111

# Message Type Specific Flags
NO_SEQUENCE = 0b0000  # no check sequence
POS_SEQUENCE = 0b0001
NEG_SEQUENCE = 0b0010
NEG_SEQUENCE_1 = 0b0011

# Message Serialization
NO_SERIALIZATION = 0b0000
JSON = 0b0001
THRIFT = 0b0011
CUSTOM_TYPE = 0b1111

# Message Compression
NO_COMPRESSION = 0b0000
GZIP = 0b0001
CUSTOM_COMPRESSION = 0b1111


class AppConfig(BaseModel):
    """应用配置"""
    appid: str
    cluster: str
    token: str


class UserConfig(BaseModel):
    """用户配置"""
    uid: str


class RequestConfig(BaseModel):
    """请求配置"""
    reqid: str
    nbest: int  # 识别结果候选数目 默认为 1。
    workflow: str  # 自定义工作流
    show_language: bool
    show_utterances: bool  # 输出语音停顿、分句、分词信息
    result_type: str  # 返回结果类型  默认每次返回所有分句结果。如果想每次只返回当前分句结果，则设置 show_utterances=true 和 result_type=single；如果当前分句结果是中间结果则返回的 definite=false，如果是分句最终结果则返回的 definite=true 。
    sequence: int = 1  # 默认值


class AudioConfig(BaseModel):
    """音频配置"""
    format: str  # 音频容器格式 raw / wav / mp3 / ogg
    rate: int  # 音频采样率 默认为 16000。
    language: str
    bits: int  # 音频采样点位数 默认为 16。
    channel: int  # 音频声道数 1(mono) / 2(stereo)，默认为1。
    codec: str  # 音频编码格式 raw / opus，默认为 raw(pcm) 。


class AsrConfig(BaseModel):
    """语音服务配置"""
    app: AppConfig
    user: UserConfig
    request: RequestConfig
    audio: AudioConfig


def create_asr_config(
        appid: str,
        cluster: str,
        token: str,
        uid: str = "",
        reqid: str = "",
        nbest: int = 1,
        workflow: str = "audio_in,resample,partition,vad,fe,decode,itn,nlu_punctuate",
        show_language: bool = False,
        show_utterances: bool = False,
        result_type: str = "full",  # single, full
        audio_format: str = "pcm",  # 默认音频采集使用的pcm
        rate: int = 16000,
        language: str = "zh-CN",  # 语言 zh-CN, en-US
        bits: int = 16,
        channel: int = 1,
        codec: str = "raw",
        sequence: int = 1,
) -> AsrConfig:
    """
    创建ASR配置对象的工厂函数

    Args:
        appid: 应用ID
        cluster: 集群名称
        token: 认证token
        uid: 用户ID
        reqid: 请求ID (默认为空字符串)
        nbest: 返回的候选结果数 (默认1)
        workflow: 工作流类型 (默认"audio_in,resample,partition,vad,fe,decode,itn,nlu_punctuate")
        show_language: 是否显示语言信息 (默认False)
        show_utterances: 是否显示话语信息 (默认False)
        result_type: 结果类型 (默认"full")
        audio_format: 音频格式 (默认"wav")
        rate: 采样率 (默认16000)
        language: 语言代码 (默认"zh-CN")
        bits: 位深度 (默认16)
        channel: 声道数 (默认1)
        codec: 编解码器 (默认"raw")
        sequence: 序列号 (默认1)

    Returns:
        配置好的AsrConfig对象
    """
    return AsrConfig(
        app=AppConfig(appid=appid, cluster=cluster, token=token),
        user=UserConfig(uid=uid),
        request=RequestConfig(
            reqid=reqid,
            nbest=nbest,
            workflow=workflow,
            show_language=show_language,
            show_utterances=show_utterances,
            result_type=result_type,
            sequence=sequence
        ),
        audio=AudioConfig(
            format=audio_format,
            rate=rate,
            language=language,
            bits=bits,
            channel=channel,
            codec=codec
        )
    )


@dataclass
class AudioChunkBatcher:
    """异步安全的音频分块批处理器

    特性：
    - 线程安全的批量处理
    - 支持基于数量(max_size)的自动批处理
    - 内存高效的字节拼接
    - 完善的异常处理
    """

    chunks: Deque[bytes] = field(default_factory=deque, init=False)
    max_size: int = field(default=10)
    async_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self):
        """参数校验和初始化"""
        if self.max_size <= 0:
            raise ValueError("批处理大小必须为正整数")

    async def append(self, chunk: bytes) -> Optional[bytes]:
        """添加音频数据块，达到阈值时返回完整批次

        参数:
            chunk: 二进制音频数据块

        返回:
            当积累到max_size时返回拼接后的批次数据
            否则返回None
        """
        if not chunk:
            raise ValueError("不能添加空数据块")

        async with self.async_lock:
            self.chunks.append(chunk)

            if len(self.chunks) >= self.max_size:
                return self._take_batch()

            return None

    async def flush(self) -> bytes:
        """强制取出当前所有数据并清空缓冲区

        典型使用场景:
        - 处理结束时获取剩余数据
        - 定时批量处理
        """
        async with self.async_lock:
            return self._take_batch()

    def _take_batch(self) -> bytes:
        """内部方法：拼接并返回当前所有数据块"""
        if not self.chunks:
            return b""

        # 预分配内存提高拼接效率
        total_size = sum(len(c) for c in self.chunks)
        result = bytearray(total_size)
        offset = 0

        for chunk in self.chunks:
            result[offset:offset + len(chunk)] = chunk
            offset += len(chunk)

        self.chunks.clear()
        return bytes(result)


class ASRClient(AsyncWebSocketClient, ASR):
    """优化的ASR识别客户端（支持WebSocket流式传输）
    """

    def __init__(self, url: str, asr_config: AsrConfig):
        """初始化ASR客户端

        参数：
            url: WebSocket服务端地址 (ws:// 或 wss://)
            asr_config: ASR配置对象，需包含：
                - app.token: 认证令牌

        初始化流程：
            1. 初始化WebSocket连接
            2. 配置音频批处理器
            3. 设置空回调函数
        """
        super().__init__(url=url, token=asr_config.app.token)
        self.asr_config = asr_config

        self.chunk_batcher = AudioChunkBatcher(max_size=15)  # 30ms * 15 = 450ms

        # 回调函数
        self.text_append_callback = None  # 增量文本回调 (partial result)
        self.text_finish_callback = None  # 最终结果回调 (final result)

    async def set_uid(self, uid: str):
        self.asr_config.user.uid = uid

    def set_callbacks(self,
                      append_cb: Optional[Callable[[str], None]] = None,
                      finish_cb: Optional[Callable[[str], None]] = None) -> None:
        """设置回调函数

        参数：
            append_cb: 增量识别结果回调（每识别出一部分文本时触发）
            finish_cb: 最终识别结果回调（整句识别完成时触发）
        """
        self.text_append_callback = append_cb
        self.text_finish_callback = finish_cb

    async def close(self, code: int = 1000, reason: str = "") -> None:
        """安全关闭TTS客户端并释放所有资源
        """
        await super().close(reason="ASR 关闭")

    async def stream_start(self) -> None:
        """Initialize streaming recognition session"""
        self.asr_config.request.reqid = uuid.uuid4().hex

        header = self._generate_header()
        request_params = self.asr_config.model_dump()
        payload = json.dumps(request_params).encode()

        await self.close(reason="ASR 开始")  # asr 不支持websocket复用链接，所以每次请求都关闭链接
        await self._send_request(header, payload)

    async def stream_append(self, audio_chunk: bytes) -> None:
        """ Append audio chunk to streaming recognition """
        audio_chunk = await self.chunk_batcher.append(audio_chunk)
        if audio_chunk is None:
            return

        header = self._generate_header(message_type=CLIENT_AUDIO_ONLY_REQUEST)
        resp = await self._send_request(header, audio_chunk)
        await self._handler_resp(resp, self.text_append_callback)

    async def stream_finish(self) -> None:
        """Finalize streaming recognition session"""
        audio_chunk = await self.chunk_batcher.flush()

        header = self._generate_header(
            message_type=CLIENT_AUDIO_ONLY_REQUEST,
            message_type_specific_flags=NEG_SEQUENCE
        )
        resp = await self._send_request(header, audio_chunk)
        await self._handler_resp(resp, self.text_finish_callback)

        await self.close(reason="ASR 结束")  # asr 不支持websocket复用链接，所以每次请求都关闭链接

    async def _send_request(self, header: bytearray, payload: bytes) -> dict:
        """
        Send request and parse response
        """
        request = header
        compressed_payload = gzip.compress(payload)
        request.extend(len(compressed_payload).to_bytes(4, 'big'))
        request.extend(compressed_payload)
        resp = await self.send(request)
        return self._parse_response(resp)

    @staticmethod
    async def _handler_resp(
            resp: dict,
            callback: Optional[Callable[[Optional[str]], Any]]
    ) -> None:
        """处理ASR响应并执行回调"""
        try:
            payload = resp.get('payload_msg', {})
            if not payload or 'result' not in payload:
                log.debug("响应缺少必要字段: payload_msg.result")
                return

            # 提取结果文本
            results = payload['result']
            if not results or not isinstance(results, list):
                log.debug("无效的result字段格式")
                return

            text = results[0].get('text') if results else None
            if not text:
                log.debug("收到空文本结果")
                return

            log.debug(f"收到识别结果: {text}")

            # 执行回调
            try:
                await callback(text)
            except Exception as e:
                log.error(f"回调执行失败: {e} - {traceback.format_exc()}")

        except Exception as e:
            log.error(f"响应处理异常: {e}", exc_info=True)

    @staticmethod
    def _generate_header(
            version=PROTOCOL_VERSION,
            message_type=CLIENT_FULL_REQUEST,
            message_type_specific_flags=NO_SEQUENCE,
            serial_method=JSON,
            compression_type=GZIP,
            reserved_data=0x00,
            extension_header=bytes()
    ):
        """
        protocol_version(4 bits), header_size(4 bits),
        message_type(4 bits), message_type_specific_flags(4 bits)
        serialization_method(4 bits) message_compression(4 bits)
        reserved （8bits) 保留字段
        header_extensions 扩展头(大小等于 8 * 4 * (header_size - 1) )
        """
        header = bytearray()
        header_size = int(len(extension_header) / 4) + 1
        header.append((version << 4) | header_size)
        header.append((message_type << 4) | message_type_specific_flags)
        header.append((serial_method << 4) | compression_type)
        header.append(reserved_data)
        header.extend(extension_header)
        return header

    @staticmethod
    def _parse_response(resp: bytes) -> dict:
        """
        protocol_version(4 bits), header_size(4 bits),
        message_type(4 bits), message_type_specific_flags(4 bits)
        serialization_method(4 bits) message_compression(4 bits)
        reserved （8bits) 保留字段
        header_extensions 扩展头(大小等于 8 * 4 * (header_size - 1) )
        payload 类似与http 请求体
        """
        protocol_version = resp[0] >> 4
        header_size = resp[0] & 0x0f
        message_type = resp[1] >> 4
        message_type_specific_flags = resp[1] & 0x0f
        serialization_method = resp[2] >> 4
        message_compression = resp[2] & 0x0f
        reserved = resp[3]
        header_extensions = resp[4:header_size * 4]
        payload = resp[header_size * 4:]

        result = {}
        payload_msg = None
        payload_size = 0

        if message_type == SERVER_FULL_RESPONSE:
            payload_size = int.from_bytes(payload[:4], "big", signed=True)
            payload_msg = payload[4:]
        elif message_type == SERVER_ACK:
            seq = int.from_bytes(payload[:4], "big", signed=True)
            result['seq'] = seq
            if len(payload) >= 8:
                payload_size = int.from_bytes(payload[4:8], "big", signed=False)
                payload_msg = payload[8:]
        elif message_type == SERVER_ERROR_RESPONSE:
            code = int.from_bytes(payload[:4], "big", signed=False)
            result['code'] = code
            payload_size = int.from_bytes(payload[4:8], "big", signed=False)
            payload_msg = payload[8:]

        if payload_msg is None:
            return result

        if message_compression == GZIP:
            payload_msg = gzip.decompress(payload_msg)

        if serialization_method == JSON:
            payload_msg = json.loads(str(payload_msg, "utf-8"))
        elif serialization_method != NO_SERIALIZATION:
            payload_msg = str(payload_msg, "utf-8")

        result['payload_msg'] = payload_msg
        result['payload_size'] = payload_size
        return result
