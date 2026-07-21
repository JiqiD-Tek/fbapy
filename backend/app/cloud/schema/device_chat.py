# -*- coding: UTF-8 -*-
"""
Device chat schemas.
"""

from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CreateDeviceChatParam(SchemaBase):
    """Create device chat request."""

    toy_id: int = Field(gt=0, description='Toy ID')
    user_message: str = Field(min_length=1, description='User message content')
    reply_message: str = Field(min_length=1, description='Reply message content')


class GetDeviceChatDetail(SchemaBase):
    """Device chat detail."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='Device chat ID')
    device_id: int = Field(description='Device ID')
    toy_id: int = Field(description='Toy ID')
    user_message: str = Field(description='User message content')
    reply_message: str = Field(description='Reply message content')
    user_id: int | None = Field(None, description='User ID')
    baby_id: int | None = Field(None, description='Baby ID')
    created_time: datetime = Field(description='Created time')
