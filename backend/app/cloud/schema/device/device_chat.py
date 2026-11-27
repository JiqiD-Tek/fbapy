# -*- coding: UTF-8 -*-
"""设备聊天数据结构。"""

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, field_validator

from backend.common.schema import SchemaBase


def _strip_required_text(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


class DeviceChatReply(SchemaBase):
    """设备聊天轮次中的玩偶回复。"""

    toy_id: int = Field(gt=0, description='玩偶 ID')
    reply_message: str = Field(min_length=1, description='回复消息内容')

    @field_validator('reply_message', mode='before')
    @classmethod
    def strip_reply_message(cls, value: Any) -> Any:
        return _strip_required_text(value)


class DeviceChatContent(SchemaBase):
    """一轮用户聊天及所有玩偶回复的内容。"""

    user_message: str = Field(min_length=1, description='用户消息内容')
    replies: list[DeviceChatReply] = Field(min_length=1, description='玩偶回复列表')

    @field_validator('user_message', mode='before')
    @classmethod
    def strip_user_message(cls, value: Any) -> Any:
        return _strip_required_text(value)


class CreateDeviceChatParam(SchemaBase):
    """创建设备聊天记录请求。"""

    content: DeviceChatContent = Field(description='设备聊天轮次内容')


class DeviceChatToyInfo(SchemaBase):
    """设备聊天记录中的玩偶信息。"""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='玩偶 ID')
    series_id: int | None = Field(None, description='玩偶系列 ID')
    name: str | None = Field(None, description='玩偶名称')
    avatar_url: str | None = Field(None, description='玩偶头像地址')
    summary: str | None = Field(None, description='玩偶简介')


class DeviceChatReplyDetail(DeviceChatReply):
    """包含关联玩偶信息的回复。"""

    toy: DeviceChatToyInfo | None = Field(None, description='玩偶信息')


class DeviceChatContentDetail(DeviceChatContent):
    """返回给客户端的设备聊天内容。"""

    replies: list[DeviceChatReplyDetail] = Field(min_length=1, description='玩偶回复列表')


class GetDeviceChatDetail(SchemaBase):
    """设备聊天详情。"""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='设备聊天记录 ID')
    device_id: int = Field(description='设备 ID')
    content: DeviceChatContentDetail = Field(description='设备聊天轮次内容')
    user_id: int | None = Field(None, description='用户 ID')
    baby_id: int | None = Field(None, description='宝宝 ID')
    created_time: datetime = Field(description='创建时间')
