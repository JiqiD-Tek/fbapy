# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : usage.py
@Author  : OpenAI
@Date    : 2026/04/23
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase


class TSDBEventDetail(SchemaBase):
    """TSDB 事件详情。"""

    ts: datetime | str | int | None = Field(None, description='事件时间')
    event_id: str | None = Field(None, description='事件 ID')
    did: str | None = Field(None, description='设备 DID')
    category: str | None = Field(None, description='事件分类')
    service: str | None = Field(None, description='服务来源')
    topic: str | None = Field(None, description='MQTT 主题')
    toy_ids: str | None = Field(None, description='本次事件选择的玩偶 ID 索引字符串')
    payload: str | None = Field(None, description='事件负载')


class TSDBUsageDetail(SchemaBase):
    """TSDB 使用记录。"""

    enabled: bool = Field(description='TSDB 是否启用')
    ready: bool = Field(description='TSDB 是否已就绪')
    error: str | None = Field(None, description='TSDB 查询错误')
    items: list[TSDBEventDetail] = Field(default_factory=list, description='TSDB 事件列表')


class VikingMemorySectionDetail(SchemaBase):
    """一段 Viking 记忆数据。"""

    enabled: bool = Field(description='Viking Memory 是否启用')
    error: str | None = Field(None, description='Viking Memory 查询错误')
    raw: dict[str, Any] = Field(default_factory=dict, description='原始返回结果')
    text: str = Field('', description='格式化后的文本结果')


class VikingUsageDetail(SchemaBase):
    """Viking 使用相关记忆。"""

    enabled: bool = Field(description='Viking Memory 是否启用')
    events: VikingMemorySectionDetail = Field(description='事件记忆')
    profiles: VikingMemorySectionDetail = Field(description='画像记忆')
