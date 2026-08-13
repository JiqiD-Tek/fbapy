# -*- coding: UTF-8 -*-
"""
Device chat schemas.
"""

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, field_validator

from backend.common.schema import SchemaBase


def _strip_required_text(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


class DeviceChatReply(SchemaBase):
    """A toy reply in a device chat turn."""

    toy_id: int = Field(gt=0, description='Toy ID')
    reply_message: str = Field(min_length=1, description='Reply message content')

    @field_validator('reply_message', mode='before')
    @classmethod
    def strip_reply_message(cls, value: Any) -> Any:
        return _strip_required_text(value)


class DeviceChatContent(SchemaBase):
    """Content for one user chat turn and all toy replies."""

    user_message: str = Field(min_length=1, description='User message content')
    replies: list[DeviceChatReply] = Field(min_length=1, description='Toy reply list')

    @field_validator('user_message', mode='before')
    @classmethod
    def strip_user_message(cls, value: Any) -> Any:
        return _strip_required_text(value)


class CreateDeviceChatParam(SchemaBase):
    """Create device chat request."""

    content: DeviceChatContent = Field(description='Device chat turn content')


class DeviceChatToyInfo(SchemaBase):
    """Toy info attached to a device chat record."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='Toy ID')
    series_id: int | None = Field(None, description='Toy series ID')
    name: str | None = Field(None, description='Toy name')
    avatar_url: str | None = Field(None, description='Toy avatar URL')
    summary: str | None = Field(None, description='Toy summary')
    nfc_code: str | None = Field(None, description='Toy NFC code')


class DeviceChatReplyDetail(DeviceChatReply):
    """A toy reply with the related toy information."""

    toy: DeviceChatToyInfo | None = Field(None, description='Toy info')


class DeviceChatContentDetail(DeviceChatContent):
    """Device chat content returned to clients."""

    replies: list[DeviceChatReplyDetail] = Field(min_length=1, description='Toy reply list')


class GetDeviceChatDetail(SchemaBase):
    """Device chat detail."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='Device chat ID')
    device_id: int = Field(description='Device ID')
    content: DeviceChatContentDetail = Field(description='Device chat turn content')
    user_id: int | None = Field(None, description='User ID')
    baby_id: int | None = Field(None, description='Baby ID')
    created_time: datetime = Field(description='Created time')
