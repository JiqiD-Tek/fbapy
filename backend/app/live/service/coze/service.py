# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：service.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/19 15:11
"""

import json
import traceback

from typing import Optional, Dict, Callable
from fastapi import WebSocket, WebSocketDisconnect

from backend.common.log import log

from backend.common.wscore.gateway import connection_gateway
from backend.common.wscore.coze.models import WebsocketsEventType, WebsocketsEvent


class CozeService(object):

    def __init__(self):
        self._on_event: Optional[Dict[WebsocketsEventType, Callable]] = self.to_dict()

    async def receive_loop(self, websocket: WebSocket) -> None:
        """ 接收消息 """
        log.debug(f"Connected to {websocket.client}")
        conn = await connection_gateway.connect(websocket)

        try:
            async for data in connection_gateway.read_text(conn.uid):
                message = json.loads(data)
                event_type = message.get("event_type")
                log.debug(f"receive event, uid={conn.uid}, type={event_type}")

                event = self.load_event(message)
                handler = self._on_event.get(event_type)
                if event and handler:
                    await handler(conn.uid, event)
        except WebSocketDisconnect as e:
            log.debug(f"连接断开 [UID:{conn.uid} - {e}]", )
        except Exception as e:
            log.error(f"连接错误 [UID:{conn.uid} - {e} - {traceback.format_exc()}]", )
        finally:
            await connection_gateway.safe_disconnect(conn.uid, websocket)

    def load_event(self, message: dict) -> Optional[WebsocketsEvent]:
        """ 转换成event 对象 """
        return None

    async def on_client_error(self, uid: str, e: Exception):
        log.error(f"Client {uid}, Error occurred: {str(e)}")
        log.error(f"Stack trace:\n{traceback.format_exc()}")

    def to_dict(
            self, origin: Optional[Dict[WebsocketsEventType, Callable]] = None
    ) -> Optional[Dict[WebsocketsEventType, Callable]]:
        res = {
            WebsocketsEventType.CLIENT_ERROR: self.on_client_error,
        }

        res.update(origin or {})
        return res
