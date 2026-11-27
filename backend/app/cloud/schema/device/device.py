# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device.py
@Author  : guhua@jiqid.com
@Date    : 2025/12/04
"""

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.app.cloud.schema.user import GetUserInfoDetail
from backend.common.schema import SchemaBase


class DeviceSchemaBase(SchemaBase):
    """设备基础数据结构。"""

    did: str = Field(description='设备 DID')
    sn: str = Field(description='设备序列号')
    mac: str = Field(description='设备 MAC 地址')
    model: str = Field(description='设备型号')

    name: str | None = Field(None, description='设备名称')
    firmware: str | None = Field(None, description='固件版本')
    hardware: str | None = Field(None, description='硬件版本')


class DeviceCredentialsParam(SchemaBase):
    """创建设备凭证请求。"""

    mac: str = Field(description='MAC 地址')


class DeviceCredentialsDetail(SchemaBase):
    """设备凭证详情。"""

    mac: str = Field(description='标准化 MAC 地址')
    did: str = Field(description='设备 DID')
    key: str = Field(description='设备密钥')


class CreateDeviceParam(DeviceSchemaBase):
    """创建设备请求。"""


class UpdateDeviceParam(DeviceSchemaBase):
    """更新设备请求。"""

    did: str | None = Field(None, description='设备 DID')
    sn: str | None = Field(None, description='设备序列号')
    mac: str | None = Field(None, description='设备 MAC 地址')
    model: str | None = Field(None, description='设备型号')


class UpdateFirmwareParam(SchemaBase):
    """更新固件请求。"""

    firmware: str = Field(description='固件版本')
    hardware: str = Field(description='硬件版本')


class DeleteDeviceParam(SchemaBase):
    """删除设备请求。"""

    pks: list[int] = Field(description='设备 ID 列表')


class GetDeviceDetail(DeviceSchemaBase):
    """设备详情。"""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='设备 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetDeviceBindStateDetail(SchemaBase):
    """设备绑定状态。"""

    is_bound: bool = Field(description='设备是否已绑定用户')
    user: GetUserInfoDetail | None = Field(None, description='已绑定的用户信息')


class DeviceToyUnlockParam(SchemaBase):
    toy_id: int = Field(gt=0, description='玩偶 ID')


class DeviceCommandRequest(SchemaBase):
    """通用设备命令请求。"""

    service: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_.-]+$', description='设备服务名')
    action: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_.-]+$', description='设备动作名')
    payload: dict[str, Any] = Field(default_factory=dict, description='透传给设备的业务参数')
    timeout: float = Field(default=10.0, gt=0, le=30.0, description='等待设备响应的秒数')


class DeviceToyListItem(SchemaBase):
    toy_id: int = Field(description='玩偶 ID')
    series_id: int | None = Field(None, description='玩偶系列 ID')
    name: str | None = Field(None, description='玩偶名称')
    avatar_url: str | None = Field(None, description='玩偶头像地址')
    summary: str | None = Field(None, description='玩偶简介')
    is_unlocked: bool = Field(description='玩偶是否已在设备上解锁')
    unlocked_at: datetime | None = Field(None, description='解锁时间')
