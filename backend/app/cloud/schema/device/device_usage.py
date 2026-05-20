# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device_usage.py
@Author  : OpenAI
@Date    : 2026/01/26 16:30
"""

import enum

from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class UsageStatus(str, enum.Enum):
    ACTIVE = 'ACTIVE'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'


class DeviceUsageSchemaBase(SchemaBase):
    device_did: str = Field(description='设备编码')
    start_time: datetime | None = Field(None, description='开始使用时间')
    end_time: datetime | None = Field(None, description='结束使用时间')
    apply_quota: int = Field(0, ge=0, description='申请使用时长（秒）')
    actual_quota: int = Field(0, ge=0, description='实际使用时长（秒）')
    status: UsageStatus = Field(UsageStatus.ACTIVE, description='使用状态')
    remark: str | None = Field(None, description='备注')


class CreateDeviceUsageParam(DeviceUsageSchemaBase):
    pass


class UpdateDeviceUsageParam(SchemaBase):
    end_time: datetime | None = Field(None, description='结束使用时间')
    actual_quota: int | None = Field(None, ge=0, description='计费时长（秒）')
    status: UsageStatus | None = Field(None, description='使用状态')
    remark: str | None = Field(None, description='备注')


class DeleteDeviceUsageParam(SchemaBase):
    pks: list[int] = Field(description='使用记录 ID 列表')


class GetDeviceUsageDetail(DeviceUsageSchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='使用记录 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
