# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : baby.py
@Author  : OpenAI
@Date    : 2026/04/17
"""

from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class BabySchemaBase(SchemaBase):
    """宝宝基础模型"""

    name: str = Field(description='宝宝姓名')
    nickname: str | None = Field(None, description='宝宝昵称')
    avatar: str | None = Field(None, description='头像')
    sex: int | None = Field(None, description='性别(0未知 1男 2女)')
    birthday: datetime | None = Field(None, description='生日')
    remark: str | None = Field(None, description='备注')


class CreateBabyParam(BabySchemaBase):
    """创建宝宝参数"""

    device_id: int = Field(description='已绑定设备 ID')


class UpdateBabyParam(SchemaBase):
    """更新宝宝参数"""

    name: str | None = Field(None, description='宝宝姓名')
    nickname: str | None = Field(None, description='宝宝昵称')
    avatar: str | None = Field(None, description='头像')
    sex: int | None = Field(None, description='性别(0未知 1男 2女)')
    birthday: datetime | None = Field(None, description='生日')
    remark: str | None = Field(None, description='备注')


class DeviceBabyParam(SchemaBase):
    """设备宝宝关系参数"""

    device_id: int = Field(description='设备 ID')
    baby_id: int = Field(description='宝宝 ID')


class GetBabyDetail(BabySchemaBase):
    """宝宝详情"""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='宝宝 ID')
    user_id: int = Field(description='用户 ID')
    device_id: int | None = Field(None, description='设备 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
