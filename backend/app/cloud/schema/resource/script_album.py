# -*- coding: UTF-8 -*-
"""剧本专辑数据结构。"""

from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from backend.common.schema import SchemaBase


def normalize_toy_ids(value: list[int] | None) -> list[int] | None:
    """去重并排序玩偶 ID。"""
    if value is None:
        return None
    return sorted(dict.fromkeys(int(toy_id) for toy_id in value))


class ScriptAlbumSchemaBase(SchemaBase):
    title: str = Field(min_length=1, max_length=256, description='专辑标题')
    toy_ids: list[int] = Field(min_length=1, description='专辑适用的玩偶 ID 列表')
    description: str | None = Field(None, description='专辑简介')
    cover_url: str | None = Field(None, max_length=512, description='专辑封面地址')
    author: str | None = Field(None, max_length=128, description='作者')
    status: int = Field(default=1, ge=0, le=1, description='状态：0 禁用，1 启用')
    remark: str | None = Field(None, max_length=500, description='备注')

    @field_validator('toy_ids')
    @classmethod
    def normalize_album_toy_ids(cls, value: list[int]) -> list[int]:
        normalized = normalize_toy_ids(value) or []
        if any(toy_id <= 0 for toy_id in normalized):
            raise ValueError('玩偶 ID 必须大于 0')
        return normalized


class CreateScriptAlbumParam(ScriptAlbumSchemaBase):
    pass


class UpdateScriptAlbumParam(SchemaBase):
    title: str | None = Field(None, min_length=1, max_length=256, description='专辑标题')
    toy_ids: list[int] | None = Field(None, min_length=1, description='专辑适用的玩偶 ID 列表')
    description: str | None = Field(None, description='专辑简介')
    cover_url: str | None = Field(None, max_length=512, description='专辑封面地址')
    author: str | None = Field(None, max_length=128, description='作者')
    status: int | None = Field(None, ge=0, le=1, description='状态：0 禁用，1 启用')
    remark: str | None = Field(None, max_length=500, description='备注')

    @field_validator('toy_ids')
    @classmethod
    def normalize_album_toy_ids(cls, value: list[int] | None) -> list[int] | None:
        normalized = normalize_toy_ids(value)
        if normalized is not None and any(toy_id <= 0 for toy_id in normalized):
            raise ValueError('玩偶 ID 必须大于 0')
        return normalized


class GetScriptAlbumDetail(ScriptAlbumSchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='剧本专辑 ID')
    track_count: int = Field(description='剧本数量')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
