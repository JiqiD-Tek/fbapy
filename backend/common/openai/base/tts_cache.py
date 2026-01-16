# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : tts_cache.py
@Author  : guhua@jiqid.com
@Date    : 2025/06/25 14:42
"""
import uuid
import asyncio

from collections import deque
from cachetools import TTLCache
from contextlib import asynccontextmanager, suppress
from typing import Optional, AsyncGenerator

from backend.common.log import log


class TTSCache:
    """TTS语音合成缓存系统（线程安全 + 自动过期） """

    def __init__(self, maxsize: int = 10, ttl: float = 3600):
        """初始化TTS缓存

        参数:
            maxsize: 最大缓存容量（按请求数计算）
                    建议值：
                    - 小型应用：50-100
                    - 中型应用：100-500
                    - 大型应用：500+
            ttl: 缓存存活时间(秒)，默认1小时
                 建议根据业务需求调整：
                 - 实时性要求高：300-900秒
                 - 内容更新频率低：3600+秒

        实现说明：
        - 使用asyncio时间戳保证事件循环一致性
        - 双层级缓存结构（请求ID -> 音频队列）
        """
        self._request_id: Optional[str] = None

        # 事件循环引用
        self._loop = asyncio.get_running_loop()
        self._audio_queues: TTLCache[str, asyncio.Queue[bytes]] = TTLCache(
            maxsize=maxsize,
            ttl=ttl,
            timer=lambda: self._loop.time(),  # 与事件循环时间同步
        )
        self._lock = asyncio.Lock()  # 异步互斥锁

    @property
    def request_id(self) -> Optional[str]:
        """获取当前活跃的请求ID（线程安全）

        返回：
            当前请求ID字符串，格式为"tts_req_<UUID>"；
            如果没有活跃请求则返回None
        """
        return self._request_id

    async def create_new_request(self, maxsize: int = 10_000) -> str:
        """创建新的语音合成请求会话

        参数：
            maxsize: 音频队列容量（默认10000个数据块）
                    建议根据音频特性设置：
                    - 高码率音频(如48kHz)：建议500-2000
                    - 低码率音频(如16kHz)：建议300-1000

        返回：
            新生成的请求ID字符串
        """
        async with self._lock:
            self._request_id = f"tts_req_{uuid.uuid4().hex}"
            self._audio_queues[self._request_id] = asyncio.Queue(maxsize=maxsize)
            return self._request_id

    @asynccontextmanager
    async def stream_audio_generator(
            self,
            request_id: Optional[str] = None,
            timeout: Optional[float] = 30.,
    ) -> AsyncGenerator[AsyncGenerator[bytes, None], None]:
        """流式音频生成器上下文管理器（带数据缓存和恢复功能）

        参数：
            request_id: 指定请求ID，默认使用当前活跃请求
            timeout: 单次数据获取超时时间(秒)，默认30秒

        返回：
            异步生成器，每次迭代返回音频数据块(bytes)
        """
        target_id = request_id or self._request_id
        if not target_id:
            raise ValueError("必须指定有效的请求ID")

        queue = self._audio_queues.get(target_id)
        if queue is None:
            raise ValueError(f"请求{target_id}对应的音频队列不存在")

        log.debug(f"读取音频长度: {queue.qsize()}")

        async def _generator() -> AsyncGenerator[bytes, None]:
            cache = deque()
            try:
                while True:
                    chunk = await asyncio.wait_for(
                        queue.get(),
                        timeout=timeout
                    )
                    cache.append(chunk)

                    if chunk == b"":  # 结束信号
                        log.debug(f"读取音频结束信号")
                        break

                    yield chunk

            except asyncio.CancelledError:
                log.info(f"客户端中断连接，request_id={target_id}")
            except Exception as e:
                log.error(f"音频流生成异常 - {e}", exc_info=True)
                raise
            finally:
                # 恢复未消费数据（如果队列已空）
                if cache and queue.empty():
                    for data in cache:
                        queue.put_nowait(data)
                log.debug(f"恢复音频长度: {queue.qsize()}")

        try:
            yield _generator()
        finally:
            log.debug(f"音频流生成器关闭，request_id={target_id}")

    async def append_audio_delta(self, delta: bytes) -> None:
        """向当前语音请求队列追加音频数据块

            参数:
                delta: 二进制音频数据块，格式应为PCM/WAV等系统支持的格式
        """
        if self._request_id is None:
            raise ValueError("必须指定有效的请求ID")

        queue = self._audio_queues.get(self._request_id)
        if queue is None:
            raise ValueError(f"请求{self._request_id}对应的音频队列不存在")

        try:
            # 使用put_nowait避免阻塞，队列满时会抛出QueueFull异常
            queue.put_nowait(delta)
        except asyncio.QueueFull:
            log.error(f"音频队列已满，丢弃数据块 (request_id={self._request_id})")
        except Exception as e:
            log.error(f"追加音频数据异常 - {e}", exc_info=True)
            raise

    async def close(self) -> bool:
        """安全关闭并清理所有TTS缓存资源"""
        try:
            async with self._lock:
                # 清空所有队列
                for queue in self._audio_queues.values():
                    while not queue.empty():
                        with suppress(Exception):  # 安全忽略所有队列操作异常
                            queue.get_nowait()

                self._audio_queues.clear()
                self._request_id = None
                log.debug(f"TTS缓存已安全关闭")

            return True

        except Exception as e:
            log.error(f"缓存关闭时发生异常 - {e}", exc_info=True)
            return False
