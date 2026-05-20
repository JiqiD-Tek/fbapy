# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device_recharge.py
@Author  : OpenAI
@Date    : 2026/01/26 16:30
"""

import enum

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class RechargeType(str, enum.Enum):
    PAYMENT = 'PAYMENT'
    MANUAL = 'MANUAL'
    PROMOTION = 'PROMOTION'


class DeviceRechargeSchemaBase(SchemaBase):
    device_did: str = Field(description='设备编码')
    amount: int = Field(ge=0, description='充值额度')
    price: int = Field(ge=0, description='单价')
    quota_before: int = Field(ge=0, description='充值前使用时长（秒）')
    quota_after: int = Field(ge=0, description='充值后使用时长（秒）')
    recharge_type: RechargeType = Field(RechargeType.PAYMENT, description='充值类型')
    remark: str | None = Field(None, description='备注')
    extra_data: dict[str, Any] | None = Field(None, description='扩展数据')


class CreateDeviceRechargeParam(DeviceRechargeSchemaBase):
    pass


class UpdateDeviceRechargeParam(SchemaBase):
    device_did: str | None = Field(None, description='设备编码')
    amount: int | None = Field(None, ge=0, description='充值额度')
    price: int | None = Field(None, ge=0, description='单价')
    quota_before: int | None = Field(None, ge=0, description='充值前使用时长（秒）')
    quota_after: int | None = Field(None, ge=0, description='充值后使用时长（秒）')
    recharge_type: RechargeType | None = Field(None, description='充值类型')
    remark: str | None = Field(None, description='备注')
    extra_data: dict[str, Any] | None = Field(None, description='扩展数据')


class DeleteDeviceRechargeParam(SchemaBase):
    pks: list[int] = Field(description='充值记录 ID 列表')


class GetDeviceRechargeDetail(DeviceRechargeSchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='充值记录 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
