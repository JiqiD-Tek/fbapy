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
from backend.app.live.agents.core.utils import aio
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

        self._event_ch = aio.Chan[WebsocketsEvent]()
        self._task = asyncio.create_task(self._send_loop(), name=f"SendLoop-{self.uid}")

        self._last_activity: float = time.monotonic()

    async def _send_loop(self) -> None:
        """Process outgoing message queue with timeout and error handling."""
        async for event in self._event_ch:
            if event is None:  # Termination signal
                break
            try:
                await self.safe_send_text(event.model_dump_json())
                self._last_activity = time.monotonic()
            except Exception as ex:
                log.critical(f"发送循环异常 [UID:{self.uid} - {ex} - {traceback.format_exc()}]")
                await asyncio.sleep(1)  # 错误冷却

    async def aclose(self) -> None:
        """安全关闭连接并释放资源（幂等操作）"""
        log.debug(f"通道[{self.uid}] 正在关闭连接")

        # 1. 停止发送循环
        await aio.cancel_and_wait(self._task)

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

    async def put_nowait(self, event: WebsocketsEvent):
        """Put an event into the output queue."""
        return self._event_ch.send_nowait(event)

    @property
    def last_activity(self) -> float:
        return self._last_activity
