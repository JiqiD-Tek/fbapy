# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device_usage.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/26 16:30
"""

import enum

from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# 枚举定义（与模型保持一致）
class UsageStatus(str, enum.Enum):
    """使用记录状态"""

    ACTIVE = 'ACTIVE'  # 使用中
    COMPLETED = 'COMPLETED'  # 正常结束并扣费
    FAILED = 'FAILED'  # 失败（余额不足等）
    CANCELLED = 'CANCELLED'  # 已取消


class DeviceUsageSchemaBase(SchemaBase):
    """设备使用基础模型"""

    did: str = Field(description='设备编码')

    # 使用时间信息
    start_time: datetime | None = Field(None, description='开始使用时间')
    end_time: datetime | None = Field(None, description='结束使用时间')
    apply_quota: int = Field(0, ge=0, description='申请使用时长（秒）')
    actual_quota: int = Field(0, ge=0, description='实际使用时长（秒）')

    # 状态信息
    status: UsageStatus = Field(UsageStatus.ACTIVE, description='使用状态')

    # 业务信息
    remark: str | None = Field(None, description='备注')


class CreateDeviceUsageParam(DeviceUsageSchemaBase):
    """创建设备使用记录参数"""


class UpdateDeviceUsageParam(SchemaBase):
    """更新设备使用记录参数"""

    end_time: datetime | None = Field(None, description='结束使用时间')
    actual_quota: int | None = Field(None, ge=0, description='计费时长（秒）')

    status: UsageStatus | None = Field(None, description='使用状态')
    remark: str | None = Field(None, description='备注')


class DeleteDeviceUsageParam(SchemaBase):
    """删除设备使用记录参数"""

    pks: list[int] = Field(description='使用记录 ID 列表')


class GetDeviceUsageDetail(DeviceUsageSchemaBase):
    """设备使用记录详情"""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='使用记录 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
