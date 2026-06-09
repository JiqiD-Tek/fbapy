# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device.py
@Author  : guhua@jiqid.com
@Date    : 2025/12/04
"""

from datetime import datetime

from pydantic import ConfigDict, Field

from backend.app.cloud.schema.user import GetUserInfoDetail
from backend.common.schema import SchemaBase


class DeviceSchemaBase(SchemaBase):
    """设备基础模型"""

    did: str = Field(description='设备编码')
    sn: str = Field(description='设备序列号')
    mac: str = Field(description='设备MAC地址')
    model: str = Field(description='设备型号')

    name: str | None = Field(None, description='设备名称')
    firmware: str | None = Field(None, description='固件版本')
    hardware: str | None = Field(None, description='硬件版本')

    quota: int = Field(0, description='当前使用时长（秒）')


class DeviceCredentialsParam(SchemaBase):
    """生成设备三元组参数"""

    mac: str = Field(description='MAC 地址')


class DeviceCredentialsDetail(SchemaBase):
    """设备三元组"""

    mac: str = Field(description='标准化后的 MAC 地址')
    did: str = Field(description='设备 DID')
    key: str = Field(description='设备 key')


class CreateDeviceParam(DeviceSchemaBase):
    """创建设备参数"""


class UpdateDeviceParam(DeviceSchemaBase):
    """更新设备参数"""

    # 可选字段，更新时可以不传
    did: str | None = Field(None, description='设备编码')
    sn: str | None = Field(None, description='设备序列号')
    mac: str | None = Field(None, description='设备MAC地址')
    model: str | None = Field(None, description='设备型号')


class UpdateFirmwareParam(SchemaBase):
    """更新设备固件参数"""

    firmware: str = Field(description='固件版本')
    hardware: str = Field(description='硬件版本')


class DeleteDeviceParam(SchemaBase):
    """删除设备参数"""

    pks: list[int] = Field(description='设备 ID 列表')


class GetDeviceDetail(DeviceSchemaBase):
    """设备详情"""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='设备 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetDeviceBindStateDetail(SchemaBase):
    """设备绑定状态"""

    is_bound: bool = Field(description='是否已绑定用户')
    user: GetUserInfoDetail | None = Field(None, description='绑定用户信息')
