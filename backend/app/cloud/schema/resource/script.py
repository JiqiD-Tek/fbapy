# -*- coding: UTF-8 -*-
"""剧本数据结构。"""

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, field_validator

from backend.common.schema import SchemaBase

SCRIPT_CONTENT_TYPES_DESCRIPTION = '内容类型列表：1 语言，2 科学，3 社会，4 艺术，5 健康'


def _normalize_content_types(value: list[int] | None) -> list[int] | None:
    if value is None:
        return None
    normalized = sorted(dict.fromkeys(int(content_type) for content_type in value))
    if not normalized:
        raise ValueError('内容类型列表不能为空')
    if any(content_type < 1 or content_type > 5 for content_type in normalized):
        raise ValueError('内容类型必须是 1 到 5')
    return normalized


def _strip_required_text(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


def _strip_optional_text(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip() or None
    return value


def _normalize_favorite_flag(value: Any) -> Any:
    return 0 if value is None else value


class ScriptLine(SchemaBase):
    toy_id: int = Field(gt=0, description='玩偶 ID')
    text: str = Field(min_length=1, description='台词内容')
    start_at: str | None = Field(None, description='开始时间')
    end_at: str | None = Field(None, description='结束时间')

    @field_validator('text', mode='before')
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        return _strip_required_text(value)

    @field_validator('start_at', 'end_at', mode='before')
    @classmethod
    def strip_time(cls, value: Any) -> Any:
        return _strip_optional_text(value)


class ScriptSchemaBase(SchemaBase):
    album_id: int = Field(gt=0, description='剧本专辑 ID')
    title: str = Field(min_length=1, max_length=256, description='剧本标题')
    content_types: list[int] | None = Field(None, min_length=1, description=SCRIPT_CONTENT_TYPES_DESCRIPTION)
    content: list[ScriptLine] = Field(min_length=1, description='剧本台词内容')
    device_id: int = Field(default=0, ge=0, description='设备 ID，0 表示平台')
    favorite: int = Field(default=0, ge=0, le=1, description='是否收藏：0 否，1 是')
    version: int = Field(default=1, ge=1, description='版本号')
    summary: str | None = Field(None, max_length=1000, description='剧本摘要')
    cover_url: str | None = Field(None, max_length=512, description='剧本封面地址')
    author: str | None = Field(None, max_length=128, description='作者')
    play_url: str | None = Field(None, max_length=1000, description='播放地址')
    duration: int = Field(default=0, ge=0, description='时长（秒）')
    track_no: int = Field(default=0, ge=0, description='专辑内曲目序号')
    status: int = Field(default=0, ge=0, le=2, description='状态：0 草稿，1 启用，2 禁用')
    remark: str | None = Field(None, max_length=500, description='备注')

    @field_validator('content_types')
    @classmethod
    def normalize_content_types(cls, value: list[int] | None) -> list[int] | None:
        return _normalize_content_types(value)

    @field_validator('favorite', mode='before')
    @classmethod
    def normalize_favorite(cls, value: Any) -> Any:
        return _normalize_favorite_flag(value)


class CreateScriptParam(ScriptSchemaBase):
    pass


class UpdateScriptFavoriteParam(SchemaBase):
    device_id: int = Field(gt=0, description='设备 ID')
    favorite: int = Field(ge=0, le=1, description='是否收藏：0 否，1 是')

    @field_validator('favorite', mode='before')
    @classmethod
    def normalize_favorite(cls, value: Any) -> Any:
        return _normalize_favorite_flag(value)


class UpdateScriptParam(SchemaBase):
    album_id: int | None = Field(None, gt=0, description='剧本专辑 ID')
    device_id: int | None = Field(None, ge=0, description='设备 ID，0 表示平台')
    favorite: int | None = Field(None, ge=0, le=1, description='是否收藏：0 否，1 是')
    title: str | None = Field(None, min_length=1, max_length=256, description='剧本标题')
    content_types: list[int] | None = Field(None, min_length=1, description=SCRIPT_CONTENT_TYPES_DESCRIPTION)
    version: int | None = Field(None, ge=1, description='版本号')
    summary: str | None = Field(None, max_length=1000, description='剧本摘要')
    cover_url: str | None = Field(None, max_length=512, description='剧本封面地址')
    author: str | None = Field(None, max_length=128, description='作者')
    play_url: str | None = Field(None, max_length=1000, description='播放地址')
    duration: int | None = Field(None, ge=0, description='时长（秒）')
    track_no: int | None = Field(None, ge=0, description='专辑内曲目序号')
    content: list[ScriptLine] | None = Field(None, min_length=1, description='剧本台词内容')
    status: int | None = Field(None, ge=0, le=2, description='状态：0 草稿，1 启用，2 禁用')
    remark: str | None = Field(None, max_length=500, description='备注')

    @field_validator('content_types')
    @classmethod
    def normalize_content_types(cls, value: list[int] | None) -> list[int] | None:
        return _normalize_content_types(value)

    @field_validator('favorite', mode='before')
    @classmethod
    def normalize_favorite(cls, value: Any) -> Any:
        return _normalize_favorite_flag(value)


class GetScriptDetail(ScriptSchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    # 兼容迁移前的历史剧本；创建剧本时仍要求填写专辑 ID。
    album_id: int | None = Field(None, description='剧本专辑 ID')
    duration: int | None = Field(None, description='时长（秒）')
    track_no: int | None = Field(None, description='专辑内曲目序号')
    id: int = Field(description='剧本 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
