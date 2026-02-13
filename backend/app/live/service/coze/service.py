# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：service.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/19 15:11
"""

import json
import traceback

from collections.abc import Callable

from fastapi import WebSocket, WebSocketDisconnect

from backend.app.live.agents.net.channel_pool import channel_pool
from backend.app.live.agents.net.coze.models import WebsocketsEvent, WebsocketsEventType
from backend.common.log import log


class CozeService:
    def __init__(self) -> None:
        self._on_event: dict[WebsocketsEventType, Callable] | None = self.to_dict()

    async def receive_loop(self, websocket: WebSocket) -> None:
        """接收消息"""
        log.debug(f'Connected to {websocket.client}')
        conn = await channel_pool.connect(websocket)

        try:
            async for data in channel_pool.read_text(conn.uid):
                message = json.loads(data)
                event_type = message.get('event_type')
                log.debug(f'receive event, uid={conn.uid}, type={event_type}')

                event = self.load_event(message)
                handler = self._on_event.get(event_type)
                if event and handler:
                    await handler(conn.uid, event)
        except WebSocketDisconnect as e:
            log.debug(f'连接断开 [UID:{conn.uid} - {e}]')
        except Exception as e:
            log.error(f'连接错误 [UID:{conn.uid} - {e} - {traceback.format_exc()}]')
        finally:
            await channel_pool.safe_disconnect(conn.uid, websocket)

    def load_event(self, message: dict) -> WebsocketsEvent | None:
        """转换成event 对象"""
        return None

    async def on_client_error(self, uid: str, e: Exception) -> None:
        log.error(f'Client {uid}, Error occurred: {e!s}')
        log.error(f'Stack trace:\n{traceback.format_exc()}')

    def to_dict(
        self, origin: dict[WebsocketsEventType, Callable] | None = None
    ) -> dict[WebsocketsEventType, Callable] | None:
        res = {
            WebsocketsEventType.CLIENT_ERROR: self.on_client_error,
        }

        res.update(origin or {})
        return res
