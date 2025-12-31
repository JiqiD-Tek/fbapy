#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Project : jiqid-py
@File    : client.py
@Author  : guhua@jiqid.com
@Created : 2025/04/16 14:29
"""

import time
import asyncio
import traceback
from contextlib import suppress

from typing import Optional, Final, Union
from fastapi import WebSocket, WebSocketDisconnect

from backend.common.log import log
from backend.common.device.repository import DeviceStateRepository

from backend.common.openai import (
    open_speech_manager,
    ASRClient,
    TTSClient,
    LLMClient,
    VADClient,
)

from backend.common.wscore.coze.models import WebsocketsEvent
from backend.common.wscore.exception.errors import WebSocketErrorCode


class ClientConnection:
    """客户端连接管理

    职责：
    - 管理WebSocket连接生命周期
    - 维护AI服务客户端实例
    - 处理消息发送队列
    - 跟踪连接活跃状态
    """

    __slots__ = (
        'uid', 'websocket', 'device_repo',
        'vad_client', 'llm_client', 'asr_client', 'tts_client',
        '_loop', '_output_queue', '_send_task', '_last_activity',
        '_is_closed', '__weakref__',
    )

    def __init__(self, uid: str, websocket: WebSocket):
        """初始化连接

        Args:
            uid: 客户端唯一标识
            websocket: 客户端WebSocket连接
        """
        if not uid:
            raise ValueError("uid must be a non-empty string")

        self.uid: Final[str] = uid
        self.websocket: Final[WebSocket] = websocket
        self.device_repo: Optional[DeviceStateRepository] = DeviceStateRepository(device_id=uid)

        # AI服务客户端
        self.vad_client: Optional[VADClient] = None
        self.llm_client: Optional[LLMClient] = None
        self.asr_client: Optional[ASRClient] = None
        self.tts_client: Optional[TTSClient] = None

        self._last_activity: float = time.monotonic()
        self._output_queue: asyncio.Queue[Optional[WebsocketsEvent]] = asyncio.Queue(maxsize=1000)
        self._is_closed: bool = False

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._send_task: Optional[asyncio.Task] = None
        self._start_send_loop()

    @property
    def loop(self):
        """Lazy initialization of event loop"""
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
        return self._loop

    def _start_send_loop(self) -> None:
        """Start the message sending loop."""
        if not self._is_closed:
            self._send_task = self.loop.create_task(
                self._send_loop(), name=f"SendLoop-{self.uid}"
            )

    async def _send_loop(self) -> None:
        """Process outgoing message queue with timeout and error handling."""
        queue_timeout = 60.0

        while not self._is_closed:
            try:
                # 1. 带超时的队列获取
                event = await asyncio.wait_for(self._output_queue.get(), timeout=queue_timeout)
                if event is None:  # Termination signal
                    break

                # 2. 执行发送数据给客户端的逻辑
                try:
                    await self.safe_send_text(event.model_dump_json())
                    self._last_activity = time.monotonic()
                except Exception as ex:
                    log.error(f"消息发送失败 [UID:{self.uid} - {ex}]", )
                    await asyncio.sleep(5)  # 错误冷却
                finally:
                    # 3. 标记任务完成
                    self._output_queue.task_done()

            except asyncio.CancelledError:
                log.debug(f"发送循环被取消 [UID:{self.uid}]")
                break
            except asyncio.TimeoutError:
                # 心跳检测等逻辑可在此添加
                continue
            except Exception as e:
                log.critical(f"发送循环异常 [UID:{self.uid} - {e} - {traceback.format_exc()}]")
                await asyncio.sleep(5)  # 错误冷却

    async def init(self) -> None:
        """并行初始化 AI 客户端，防止重复初始化"""
        if self._is_closed:
            log.warning(f"[{self.uid}] 已关闭，跳过初始化")
            return

        async def _acquire(name: str, func):
            try:
                return await func(uid=self.uid)
            except Exception as e:
                log.error(f"[{self.uid}] 初始化 {name} 失败: {e}")
                return None

        # 并发获取多个服务实例
        results = await asyncio.gather(
            _acquire("VAD", open_speech_manager.acquire_vad),
            _acquire("LLM", open_speech_manager.acquire_llm),
            _acquire("ASR", open_speech_manager.acquire_asr),
            _acquire("TTS", open_speech_manager.acquire_tts),
        )

        self.vad_client, self.llm_client, self.asr_client, self.tts_client = results

    async def close(self) -> None:
        """安全关闭连接并释放资源（幂等操作）"""
        if self._is_closed:
            return
        self._is_closed = True
        log.info(f"[{self.uid}] 正在关闭连接")

        # 1. 停止发送循环
        if self._send_task and not self._send_task.done():
            self._send_task.cancel()
            with suppress(asyncio.CancelledError, asyncio.TimeoutError):
                await asyncio.wait_for(self._send_task, timeout=3.0)

        # 2. 清空队列
        while not self._output_queue.empty():
            with suppress(asyncio.QueueEmpty):
                self._output_queue.get_nowait()
                self._output_queue.task_done()

        # 3. 并发释放 AI 客户端
        async def _release(client, release_func):
            if client:
                with suppress(Exception):
                    await release_func(client)

        await asyncio.gather(
            _release(self.vad_client, open_speech_manager.release_vad),
            _release(self.llm_client, open_speech_manager.release_llm),
            _release(self.asr_client, open_speech_manager.release_asr),
            _release(self.tts_client, open_speech_manager.release_tts),
        )

        self.vad_client = self.llm_client = self.asr_client = self.tts_client = None

        # 4. 关闭 WebSocket
        await self.terminate_connection(self.websocket, WebSocketErrorCode.NORMAL_CLOSE)

        log.info(f"[{self.uid}] 连接已关闭")

    # -------------------------------------------------------------------------
    # 安全发送封装
    # -------------------------------------------------------------------------
    async def safe_send_text(self, data: str) -> None:
        await self._safe_send(data, binary=False)

    async def safe_send_bytes(self, data: bytes) -> None:
        await self._safe_send(data, binary=True)

    async def _safe_send(self, data: Union[str, bytes], binary: bool) -> None:
        if self._is_closed:
            raise RuntimeError(f"[{self.uid}] 连接已关闭，无法发送")

        try:
            if binary:
                await self.websocket.send_bytes(data)
            else:
                await self.websocket.send_text(data)
            self._last_activity = time.monotonic()
        except (WebSocketDisconnect, ConnectionError, RuntimeError) as ex:
            log.error(f"[{self.uid}] 发送失败: {ex}")
            raise

    # -------------------------------------------------------------------------
    # 工具与属性
    # -------------------------------------------------------------------------
    @staticmethod
    async def terminate_connection(websocket: WebSocket,
                                   error_code: WebSocketErrorCode,
                                   reason: str = "") -> None:
        """关闭 WebSocket"""
        with suppress(Exception):
            await asyncio.wait_for(
                websocket.close(code=error_code.code, reason=reason or error_code.reason),
                timeout=3.0
            )

    @property
    def output_queue(self) -> asyncio.Queue[WebsocketsEvent]:
        return self._output_queue

    @property
    def last_activity(self) -> float:
        return self._last_activity
