#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Project : jiqid-py
@File    : channel.py
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

from backend.app.live.agents.assistant import Assistant
from backend.app.live.agents.net.coze.models import WebsocketsEvent
from backend.app.live.agents.net.exception.errors import WebSocketErrorCode


class Channel:
    """通道连接管理 """

    def __init__(self, uid: str, websocket: WebSocket):
        """初始化连接 """
        self.uid = uid
        self.websocket: Final[WebSocket] = websocket
        self.assistant: Optional[Assistant] = None

        self._last_activity: float = time.monotonic()
        self._output_queue: asyncio.Queue[Optional[WebsocketsEvent]] = asyncio.Queue(maxsize=1000)
        self._is_closed: bool = False

        self._send_task = asyncio.create_task(self._send_loop(), name=f"SendLoop-{self.uid}")

    async def _send_loop(self) -> None:
        """Process outgoing message queue with timeout and error handling."""
        while not self._is_closed:
            try:
                # 1. 带超时的队列获取
                event = await asyncio.wait_for(self._output_queue.get(), timeout=60.0)
                if event is None:  # Termination signal
                    break

                # 2. 执行发送数据给通道的逻辑
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
        """并行初始化 AI 通道，防止重复初始化"""
        if self._is_closed:
            log.warning(f"通道[{self.uid}] 已关闭，跳过初始化")
            return

    async def aclose(self) -> None:
        """安全关闭连接并释放资源（幂等操作）"""
        if self._is_closed:
            return

        self._is_closed = True
        log.debug(f"通道[{self.uid}] 正在关闭连接")

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

        # 3. 释放助手
        if self.assistant:
            await self.assistant.aclose()

        # 4. 关闭 WebSocket
        await self.terminate_connection(self.websocket, WebSocketErrorCode.NORMAL_CLOSE)

        log.debug(f"通道[{self.uid}] 连接已关闭")

    # -------------------------------------------------------------------------
    # 安全发送封装
    # -------------------------------------------------------------------------
    async def safe_send_text(self, data: str) -> None:
        await self._safe_send(data, binary=False)

    async def safe_send_bytes(self, data: bytes) -> None:
        await self._safe_send(data, binary=True)

    async def _safe_send(self, data: Union[str, bytes], binary: bool) -> None:
        if self._is_closed:
            raise RuntimeError(f"通道[{self.uid}] 连接已关闭，无法发送")

        try:
            if binary:
                await self.websocket.send_bytes(data)
            else:
                await self.websocket.send_text(data)
            self._last_activity = time.monotonic()
        except (WebSocketDisconnect, ConnectionError, RuntimeError) as ex:
            log.error(f"[{self.uid}] 发送失败: {ex}")
            raise

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

    def put_nowait(self, event: WebsocketsEvent):
        """Put an event into the output queue."""
        return self._output_queue.put(event)

    @property
    def last_activity(self) -> float:
        return self._last_activity
