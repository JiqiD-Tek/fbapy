# -*- coding: UTF-8 -*-
"""
Device chat schemas.
"""

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, field_validator

from backend.common.schema import SchemaBase


class CreateDeviceChatParam(SchemaBase):
    """Create device chat request."""

    nfc_code: str = Field(min_length=1, max_length=64, description='Toy NFC code')
    user_message: str = Field(min_length=1, description='User message content')
    reply_message: str = Field(min_length=1, description='Reply message content')

    @field_validator('nfc_code', mode='before')
    @classmethod
    def strip_identifier(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value


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
