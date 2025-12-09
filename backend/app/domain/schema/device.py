# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device.py
@Author  : guhua@jiqid.com
@Date    : 2025/12/04
"""
from datetime import datetime
from typing import Optional

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class DeviceSchemaBase(SchemaBase):
    """设备基础模型"""

    did: str = Field(description='设备编码')
    sn: str = Field(description='设备序列号')
    mac: str = Field(description='设备MAC地址')
    model: str = Field(description='设备型号')

    name: Optional[str] = Field(None, description='设备名称')
    firmware: Optional[str] = Field(None, description='固件版本')
    hardware: Optional[str] = Field(None, description='硬件版本')
    user_id: Optional[int] = Field(None, description='设备所有者ID')


class CreateDeviceParam(DeviceSchemaBase):
    """创建设备参数"""


class UpdateDeviceParam(DeviceSchemaBase):
    """更新设备参数"""

    # 可选字段，更新时可以不传
    did: Optional[str] = Field(None, description='设备编码')
    sn: Optional[str] = Field(None, description='设备序列号')
    mac: Optional[str] = Field(None, description='设备MAC地址')
    model: Optional[str] = Field(None, description='设备型号')


class DeleteDeviceParam(SchemaBase):
    """删除设备参数"""

    pks: list[int] = Field(description='设备 ID 列表')


class GetDeviceDetail(DeviceSchemaBase):
    """设备详情"""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='设备 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: Optional[datetime] = Field(None, description='更新时间')
