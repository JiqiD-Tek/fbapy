# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : __init__.py.py
@Author  : guhua@jiqid.com
@Date    : 2025/07/25 14:41
"""
from enum import Enum
from pydantic import Field
from datetime import datetime
from pydantic import BaseModel
from typing import Literal, Any, Optional, Dict

from backend.common.log import log
from backend.common.wscore.coze.models import WebsocketsEvent, WebsocketsEventType, Message, CozeModel


class CommandType(str, Enum):
    """支持的所有命令类型枚举"""
    ALARM = "alarm"
    MUSIC = "music"
    CONTROL = "control"


class Command(CozeModel):
    """设备控制事件标准模型"""

    class Payload(BaseModel):
        """标准化命令负载结构"""
        cmd: str = Field(..., min_length=1, description="具体操作指令")
        params: Optional[Dict[str, Any]] = Field(
            description="动态参数",
            examples=[{"volume": 80}, ]
        )

    protocol: Literal["v1", "v2"] = Field(
        default="v1",  # 显式设置默认值
        description="协议版本，默认为v1"
    )
    timestamp: int = Field(
        default_factory=lambda: int(datetime.now().timestamp()),
        description="事件创建时间戳（秒）"
    )
    type: CommandType = Field(..., description="命令分类")
    payload: Payload

    @staticmethod
    def build_command(
            type: CommandType,
            cmd: str,
            params: Optional[Dict[str, Any]] = None
    ) -> "Command":
        return Command(
            type=type,
            payload=Command.Payload(
                cmd=cmd,
                params=params
            )
        )


class CtrlCreatedEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.CTRL_CREATED
    data: Message


class CtrlCompletedEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.CTRL_COMPLETED


def load_req_event(message: Dict) -> Optional[WebsocketsEvent]:
    event_id = message.get("id") or ""
    detail = WebsocketsEvent.Detail.model_validate(message.get("detail") or {})
    event_type = message.get("event_type") or ""
    data = message.get("data") or {}

    if event_type == WebsocketsEventType.CTRL_CREATED.value:
        return CtrlCreatedEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": Message.model_validate(data),
            }
        )

    log.warning(f"[v1/ctrl] unknown event, type={event_type}, logid={detail.logid}")
    return None


def load_resp_event(message: Dict) -> Optional[WebsocketsEvent]:
    event_id = message.get("id") or ""
    detail = WebsocketsEvent.Detail.model_validate(message.get("detail") or {})
    event_type = message.get("event_type") or ""

    if event_type == WebsocketsEventType.CTRL_COMPLETED.value:
        return CtrlCompletedEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
            }
        )

    log.warning(f"[v1/ctrl] unknown event, type={event_type}, logid={detail.logid}")
    return None
