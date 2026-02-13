# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device_recharge.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/26 16:30
"""

import enum

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# 枚举定义（与模型保持一致）
class RechargeType(str, enum.Enum):
    """充值类型"""

    PAYMENT = 'PAYMENT'  # 外部支付充值
    MANUAL = 'MANUAL'  # 后台手动充值
    PROMOTION = 'PROMOTION'  # 促销赠送


class DeviceRechargeSchemaBase(SchemaBase):
    """设备充值基础模型"""

    did: str = Field(description='设备编码')

    # 充值信息
    amount: int = Field(ge=0, description='充值额度')
    price: int = Field(ge=0, description='单价')
    quota_before: int = Field(ge=0, description='充值前使用时长（秒）')
    quota_after: int = Field(ge=0, description='充值后使用时长（秒）')

    # 类型和扩展信息
    recharge_type: RechargeType = Field(RechargeType.PAYMENT, description='充值类型')
    remark: str | None = Field(None, description='备注')
    extra_data: dict[str, Any] | None = Field(None, description='扩展数据')


class CreateDeviceRechargeParam(DeviceRechargeSchemaBase):
    """创建设备充值记录参数"""


class UpdateDeviceRechargeParam(SchemaBase):
    """更新设备充值记录参数"""

    did: str | None = Field(None, description='设备编码')
    amount: int | None = Field(None, ge=0, description='充值额度')
    price: int | None = Field(None, ge=0, description='单价')
    quota_before: int | None = Field(None, ge=0, description='充值前使用时长（秒）')
    quota_after: int | None = Field(None, ge=0, description='充值后使用时长（秒）')
    recharge_type: RechargeType | None = Field(None, description='充值类型')
    remark: str | None = Field(None, description='备注')
    extra_data: dict[str, Any] | None = Field(None, description='扩展数据')


class DeleteDeviceRechargeParam(SchemaBase):
    """删除设备充值记录参数"""

    pks: list[int] = Field(description='充值记录 ID 列表')


class GetDeviceRechargeDetail(DeviceRechargeSchemaBase):
    """设备充值记录详情"""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='充值记录 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
