# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : song.py
@Author  : OpenAI
@Date    : 2026/03/26
"""

from datetime import datetime

from pydantic import ConfigDict, Field

from backend.app.iot.schema.cloud.album import ContentType
from backend.common.schema import SchemaBase


class SongSchemaBase(SchemaBase):
    album_id: int | None = Field(None, description='本地专辑 ID')
    title: str = Field(description='歌曲标题')
    subtitle: str | None = Field(None, description='歌曲副标题')
    cover_url: str | None = Field(None, description='歌曲封面地址')
    play_url: str | None = Field(None, description='播放地址')
    artist: str | None = Field(None, description='歌手/主播')
    content_type: ContentType | None = Field(None, description='内容类型：儿歌、国学、英语、故事、AI生成')
    duration: int = Field(default=0, description='时长(秒)')
    track_no: int = Field(default=0, description='曲目序号')
    status: int = Field(default=1, description='状态(0禁用 1启用)')
    remark: str | None = Field(None, description='备注')


class CreateSongParam(SongSchemaBase):
    pass


class UpdateSongParam(SchemaBase):
    album_id: int | None = Field(None, description='本地专辑 ID')
    title: str | None = Field(None, description='歌曲标题')
    subtitle: str | None = Field(None, description='歌曲副标题')
    cover_url: str | None = Field(None, description='歌曲封面地址')
    play_url: str | None = Field(None, description='播放地址')
    artist: str | None = Field(None, description='歌手/主播')
    content_type: ContentType | None = Field(None, description='内容类型：儿歌、国学、英语、故事、AI生成')
    duration: int | None = Field(None, description='时长(秒)')
    track_no: int | None = Field(None, description='曲目序号')
    status: int | None = Field(None, description='状态(0禁用 1启用)')
    remark: str | None = Field(None, description='备注')


class GetSongDetail(SongSchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='歌曲 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
