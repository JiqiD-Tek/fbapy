# -*- coding: UTF-8 -*-
"""歌曲专辑数据结构。"""

import enum
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class ContentType(enum.IntEnum):
    CHILDREN_SONGS = 1
    STORY = 2
    SLEEP_SOOTHING = 3


class SongAlbumSchemaBase(SchemaBase):
    title: str = Field(description='专辑标题')
    subtitle: str | None = Field(None, description='专辑副标题')
    cover_url: str | None = Field(None, description='专辑封面地址')
    artist: str | None = Field(None, description='主播名称')
    min_age: int | None = Field(None, ge=0, description='最小适龄')
    max_age: int | None = Field(None, ge=0, description='最大适龄')
    content_type: ContentType = Field(description='内容类型：1 儿歌，2 故事，3 哄睡')
    category_name: str | None = Field(None, description='分类名称')
    tags: str | None = Field(None, description='标签，逗号分隔')
    description: str | None = Field(None, description='专辑简介')
    status: int = Field(default=1, description='状态：0 禁用，1 启用')
    remark: str | None = Field(None, description='备注')


class CreateSongAlbumParam(SongAlbumSchemaBase):
    pass


class UpdateSongAlbumParam(SchemaBase):
    title: str | None = Field(None, description='专辑标题')
    subtitle: str | None = Field(None, description='专辑副标题')
    cover_url: str | None = Field(None, description='专辑封面地址')
    artist: str | None = Field(None, description='主播名称')
    min_age: int | None = Field(None, ge=0, description='最小适龄')
    max_age: int | None = Field(None, ge=0, description='最大适龄')
    content_type: ContentType | None = Field(None, description='内容类型：1 儿歌，2 故事，3 哄睡')
    category_name: str | None = Field(None, description='分类名称')
    tags: str | None = Field(None, description='标签，逗号分隔')
    description: str | None = Field(None, description='专辑简介')
    status: int | None = Field(None, description='状态：0 禁用，1 启用')
    remark: str | None = Field(None, description='备注')


class GetSongAlbumDetail(SongAlbumSchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='歌曲专辑 ID')
    track_count: int = Field(description='歌曲数量')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
