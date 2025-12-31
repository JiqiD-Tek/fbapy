# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：tts_client.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/15 16:35
"""
import time
import uuid
import json
import gzip

import asyncio
import traceback
from contextlib import suppress

from pydantic import BaseModel
from typing import Optional, Callable, Any

from backend.common.log import log
from backend.common.openai.speech.base.tts import TTS
from backend.common.openai.speech.base.tts_cache import TTSCache
from backend.common.openai.speech.base.ws import AsyncWebSocketClient

MESSAGE_TYPES = {11: "audio-only server response", 12: "frontend server response", 15: "error message from server"}
MESSAGE_TYPE_SPECIFIC_FLAGS = {0: "no sequence number", 1: "sequence number > 0",
                               2: "last message from server (seq < 0)", 3: "sequence number < 0"}
MESSAGE_SERIALIZATION_METHODS = {0: "no serialization", 1: "JSON", 15: "custom type"}
MESSAGE_COMPRESSIONS = {0: "no compression", 1: "gzip", 15: "custom compression method"}


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
    encoding: str = "wav"  # 音频编码格式， wav / pcm / ogg_opus / mp3，默认为 pcm 注意：wav 不支持流式
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
        uid: str = "",
        text: str = "",
        reqid: str = "",
        text_type: str = "plain",
        operation: str = "submit",
        voice_type: str = "BV064_streaming",  # https://www.volcengine.com/docs/6561/97465  S_HFruD8as1 BV064_streaming
        encoding: str = "pcm",
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
        )
    )
    log.debug(f"tts config: {config}")
    return config


class TTSClient(AsyncWebSocketClient, TTS):
    """优化的TTS合成客户端（支持WebSocket流式传输）
    """

    def __init__(self, url: str, tts_config: TTSConfig):
        """初始化TTS客户端

        参数：
            url: WebSocket服务端地址 (ws:// 或 wss://)
            tts_config: TTS配置对象，需包含：
                - app.token: 认证令牌

        初始化流程：
            1. 建立WebSocket连接
            2. 初始化合成任务队列
            3. 启动后台处理任务
            4. 初始化音频缓存
        """
        super().__init__(url=url, token=tts_config.app.token)
        self.tts_config = tts_config

        # 音频回调函数
        self._audio_callback = None

        # 音频缓存系统
        self._tts_cache = TTSCache(maxsize=10, ttl=3600)

        # 合成任务队列（带背压控制）
        self._tts_queue = asyncio.Queue(maxsize=1000)

        # 状态管理
        self._is_active = asyncio.Event()
        self._is_active.set()

        # 事件循环引用
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._tts_task: Optional[asyncio.Task] = None
        self.start_tts_task()

    @property
    def loop(self):
        """Lazy initialization of event loop"""
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
        return self._loop

    @property
    def tts_cache(self) -> Optional[TTSCache]:
        return self._tts_cache

    async def set_uid(self, uid: str):
        self.tts_config.user.uid = uid

    def start_tts_task(self) -> None:
        self.loop.create_task(
            self._tts_worker(),
            name=f"TTSWorker-{id(self)}"
        )

    def set_callback(self, callback: Optional[Callable[[bytes], None]] = None):
        self._audio_callback = callback

    def stop_speaking(self):
        log.debug("停止语音合成")
        self._is_active.clear()

    async def close(self, code: int = 1000, reason: str = "") -> None:
        """安全关闭TTS客户端并释放所有资源
        """
        try:
            log.info("开始关闭TTS处理器...")

            # 1. 停止后台任务
            self._tts_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._tts_task  # 等待任务结束

            # 2. 清空处理队列
            while not self._tts_queue.empty():
                with suppress(asyncio.QueueEmpty):
                    self._tts_queue.get_nowait()
                    self._tts_queue.task_done()

            # 3. 关闭父类连接
            await super().close(reason="TTS 关闭")

            # 4. 清理缓存
            await self._tts_cache.close()

            # 5. 更新状态
            self._is_active.clear()
            log.debug("TTS处理器关闭完成")

        except Exception as e:
            log.error(f"关闭TTS处理器时发生异常: {e}", exc_info=True)
        finally:
            # 最终资源检查
            if not self._tts_task.done():
                self._tts_task.cancel()
            if not self._tts_queue.empty():
                self._tts_queue = asyncio.Queue()  # 重置队列

    async def submit(self, text: str, is_final: bool = False) -> None:
        log.debug(f"提交TTS submit合成请求: [text={text} | size={len(text)} | is_final={is_final}]")
        self._is_active.set()
        self.loop.call_soon_threadsafe(self._tts_queue.put_nowait, (text, "submit", is_final))

    async def query(self, text: str, is_final: bool = False) -> None:
        log.debug(f"提交TTS query合成请求: [text={text} | size={len(text)} | is_final={is_final}]")
        self._is_active.set()
        self.loop.call_soon_threadsafe(self._tts_queue.put_nowait, (text, "query", is_final))

    async def _tts_worker(self):
        while True:
            try:
                # 1. 安全获取队列任务（带超时防止永久阻塞）
                text, operation, is_final = await asyncio.wait_for(
                    self._tts_queue.get(),
                    timeout=60.0  # 60秒无任务则超时
                )

                # 2. 处理请求（隔离处理阶段的异常）
                try:
                    start_time = time.perf_counter()
                    request = await self._prepare_request(text, operation=operation)
                    await self._handle_request(request, is_final=is_final)
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    log.debug(f"请求处理耗时: {elapsed_ms:.2f}ms | 请求长度: {len(request)}字节")
                except Exception as ex:
                    log.error(f"请求处理失败 - {ex}", exc_info=True)

                # 3. 标记任务完成（支持队列join同步）
                self._tts_queue.task_done()

            except asyncio.CancelledError:
                log.info("TTS处理器被终止")
                break
            except asyncio.TimeoutError:
                continue
            except Exception as ex:
                log.critical(f"TTS处理器发生未捕获异常 - {ex} - {traceback.print_exc()}", exc_info=True)
                await asyncio.sleep(1)  # 避免错误循环占用CPU

    async def _handle_request(self, request: bytearray, is_final: bool = False) -> None:
        try:
            if not self._is_active.is_set():
                return

            # 1. 确保连接就绪
            await self.ensure_connection()

            # 2. 发送请求数据
            await self._conn.send(request)

            # 3. 接收响应数据流
            while True:
                try:
                    resp = await asyncio.wait_for(
                        self._conn.recv(),
                        timeout=10.0  # 防止无响应卡死
                    )
                    # 跳过非活跃状态数据
                    if not self._is_active.is_set():
                        continue

                    if self._audio_callback is None:
                        continue

                    # 4. 解析响应数据
                    done = await self._parse_response(resp, self._audio_callback)
                    if done:
                        break  # 服务端指示完成

                except asyncio.TimeoutError:
                    log.warning("TTS响应超时，可能服务端无数据")
                    break
                except Exception as e:
                    log.error(f"TTS处理器发生未捕获异常 - {e} - {traceback.format_exc()}")
                    raise

            # 5. 最终确认处理
            if (is_final
                    and self._is_active.is_set()
                    and self._audio_callback):
                await self._audio_callback(b'')  # 发送空数据表示结束

        except Exception as e:
            log.critical(f"TTS处理器发生未捕获异常 - {e} - {traceback.print_exc()}", exc_info=True)
            raise  # 保留原始异常栈

    async def _prepare_request(self, text: str, operation: str = None) -> bytearray:
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
        header_size = resp[0] & 0x0f
        message_type = resp[1] >> 4
        message_type_specific_flags = resp[1] & 0x0f
        serialization_method = resp[2] >> 4
        message_compression = resp[2] & 0x0f
        reserved = resp[3]
        header_extensions = resp[4:header_size * 4]
        payload = resp[header_size * 4:]

        log.debug(f"Protocol version: {protocol_version:#x} - version {protocol_version}")
        log.debug(f"Header size: {header_size:#x} - {header_size * 4} bytes")
        log.debug(f"Message type: {message_type:#x} - {MESSAGE_TYPES[message_type]}")
        log.debug(
            f"Message type specific flags: {message_type_specific_flags:#x} - {MESSAGE_TYPE_SPECIFIC_FLAGS[message_type_specific_flags]}")
        log.debug(
            f"Message serialization method: {serialization_method:#x} - {MESSAGE_SERIALIZATION_METHODS[serialization_method]}")
        log.debug(f"Message compression: {message_compression:#x} - {MESSAGE_COMPRESSIONS[message_compression]}")
        log.debug(f"Reserved: {reserved:#04x}")

        if header_size != 1:
            log.debug(f"Header extensions: {header_extensions}")

        if message_type == 0xb:  # audio-only server response
            if message_type_specific_flags == 0:  # no sequence number as ACK
                return False
            else:
                sequence_number = int.from_bytes(payload[:4], "big", signed=True)
                payload_size = int.from_bytes(payload[4:8], "big", signed=False)
                payload = payload[8:]
                log.debug(f"Sequence number: {sequence_number}")
                log.debug(f"Payload size: {payload_size} bytes")

            await audio_callback(payload)  # 音频合成回调函数

            return sequence_number < 0

        elif message_type == 0xf:
            code = int.from_bytes(payload[:4], "big", signed=False)
            msg_size = int.from_bytes(payload[4:8], "big", signed=False)
            error_msg = payload[8:]
            if message_compression == 1:
                error_msg = gzip.decompress(error_msg)
            error_msg = str(error_msg, "utf-8")
            log.error(f"Error message code: {code}")
            log.error(f"Error message size: {msg_size} bytes")
            log.error(f"Error message: {error_msg}")
            return True

        elif message_type == 0xc:
            msg_size = int.from_bytes(payload[:4], "big", signed=False)
            payload = payload[4:]
            if message_compression == 1:
                payload = gzip.decompress(payload)

            log.debug(f"Frontend message: {payload} - {msg_size}")
            return None

        else:
            log.debug("undefined message type!")
            return True
