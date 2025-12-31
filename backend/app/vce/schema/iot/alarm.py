# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : alarm.py
@Author  : guhua@jiqid.com
@Date    : 2025/07/25 11:11
"""
from datetime import datetime, time
from typing import Union, List

from pydantic import Field, ConfigDict

from backend.common.device.model import AlarmType
from backend.common.schema import SchemaBase


class AlarmSchemaBase(SchemaBase):
    """闹钟基础模型"""
    alarm_type: AlarmType = Field(description='闹钟类型 重复周期型: 0, 单次非周期型: 1')
    trigger: Union[datetime, time] = Field(description='支持绝对时间或相对时间')
    repeat: List[int] = Field(description='重复日期（0-6对应周一到周日）')
    label: str = Field(description='闹钟标签')


class CreateAlarmParam(AlarmSchemaBase):
    """创建闹钟参数"""


class UpdateAlarmParam(AlarmSchemaBase):
    """更新闹钟参数"""
    id: str = Field(description='闹钟 ID')


class DeleteAlarmParam(SchemaBase):
    """删除闹钟参数"""

    pks: list[str] = Field(description='闹钟 ID 列表')


class GetAlarmDetail(AlarmSchemaBase):
    """闹钟详情"""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description='闹钟 ID')
