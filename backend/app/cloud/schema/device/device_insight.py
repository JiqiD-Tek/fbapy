# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device_insight.py
@Author  : OpenAI
@Date    : 2026/04/23
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from backend.app.cloud.schema.device.device import GetDeviceDetail
from backend.common.schema import SchemaBase


class DeviceTSDBEventDetail(SchemaBase):
    """TSDB device event detail."""

    ts: datetime | str | int | None = Field(None, description='事件时间')
    event_id: str | None = Field(None, description='事件 ID')
    did: str | None = Field(None, description='设备 DID')
    direction: str | None = Field(None, description='消息方向')
    category: str | None = Field(None, description='事件分类')
    service: str | None = Field(None, description='服务来源')
    topic: str | None = Field(None, description='MQTT topic')
    payload: str | None = Field(None, description='事件负载')


class DeviceTSDBInsightDetail(SchemaBase):
    """TSDB insight section."""

    enabled: bool = Field(description='TSDB 是否启用')
    ready: bool = Field(description='TSDB 是否已就绪')
    error: str | None = Field(None, description='TSDB 查询错误')
    items: list[DeviceTSDBEventDetail] = Field(default_factory=list, description='TSDB 事件列表')


class DeviceVikingMemorySectionDetail(SchemaBase):
    """One Viking memory section."""

    enabled: bool = Field(description='Viking Memory 是否启用')
    error: str | None = Field(None, description='Viking Memory 查询错误')
    raw: dict[str, Any] = Field(default_factory=dict, description='原始返回结果')
    text: str = Field('', description='格式化后的文本结果')


class DeviceVikingInsightDetail(SchemaBase):
    """Viking memory insight section."""

    enabled: bool = Field(description='Viking Memory 是否启用')
    events: DeviceVikingMemorySectionDetail = Field(description='事件记忆')
    profiles: DeviceVikingMemorySectionDetail = Field(description='画像记忆')


class GetDeviceInsightDetail(SchemaBase):
    """Aggregated device insight response."""

    tsdb: DeviceTSDBInsightDetail = Field(description='TSDB 数据')
    viking: DeviceVikingInsightDetail = Field(description='Viking 数据')
