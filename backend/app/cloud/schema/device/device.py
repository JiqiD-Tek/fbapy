# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device.py
@Author  : guhua@jiqid.com
@Date    : 2025/12/04
"""

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, field_validator

from backend.app.cloud.schema.user import GetUserInfoDetail
from backend.common.schema import SchemaBase


class DeviceSchemaBase(SchemaBase):
    """Device base schema."""

    did: str = Field(description='Device DID')
    sn: str = Field(description='Device serial number')
    mac: str = Field(description='Device MAC address')
    model: str = Field(description='Device model')

    name: str | None = Field(None, description='Device name')
    firmware: str | None = Field(None, description='Firmware version')
    hardware: str | None = Field(None, description='Hardware version')

    quota: int = Field(0, description='Current usage duration in seconds')


class DeviceCredentialsParam(SchemaBase):
    """Create device credentials request."""

    mac: str = Field(description='MAC address')


class DeviceCredentialsDetail(SchemaBase):
    """Device credentials detail."""

    mac: str = Field(description='Normalized MAC address')
    did: str = Field(description='Device DID')
    key: str = Field(description='Device key')


class CreateDeviceParam(DeviceSchemaBase):
    """Create device request."""


class UpdateDeviceParam(DeviceSchemaBase):
    """Update device request."""

    did: str | None = Field(None, description='Device DID')
    sn: str | None = Field(None, description='Device serial number')
    mac: str | None = Field(None, description='Device MAC address')
    model: str | None = Field(None, description='Device model')


class UpdateFirmwareParam(SchemaBase):
    """Update firmware request."""

    firmware: str = Field(description='Firmware version')
    hardware: str = Field(description='Hardware version')


class DeleteDeviceParam(SchemaBase):
    """Delete device request."""

    pks: list[int] = Field(description='Device ID list')


class GetDeviceDetail(DeviceSchemaBase):
    """Device detail."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='Device ID')
    created_time: datetime = Field(description='Created time')
    updated_time: datetime | None = Field(None, description='Updated time')


class GetDeviceBindStateDetail(SchemaBase):
    """Device binding state."""

    is_bound: bool = Field(description='Whether the device is bound to a user')
    user: GetUserInfoDetail | None = Field(None, description='Bound user info')


class DeviceToyUnlockParam(SchemaBase):
    nfc_code: str = Field(min_length=1, max_length=64, description='Toy NFC code')

    @field_validator('nfc_code', mode='before')
    @classmethod
    def strip_nfc_code(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value


class DeviceToyListItem(SchemaBase):
    toy_id: int = Field(description='Toy ID')
    series_id: int | None = Field(None, description='Toy series ID')
    name: str | None = Field(None, description='Toy name')
    avatar_url: str | None = Field(None, description='Toy avatar URL')
    summary: str | None = Field(None, description='Toy summary')
    is_unlocked: bool = Field(description='Whether the toy has been unlocked on the device')
    unlocked_at: datetime | None = Field(None, description='Unlock time')
