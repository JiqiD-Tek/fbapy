# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : song.py
@Author  : OpenAI
@Date    : 2026/03/26
"""

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, field_validator

from backend.app.cloud.schema.resource.album import ContentType
from backend.common.schema import SchemaBase


class SongScriptGroup(SchemaBase):
    speaker: str = Field(min_length=1, max_length=128, description='音色 ID')
    speech_rate: int = Field(default=0, description='语速')
    loudness_rate: int = Field(default=0, description='音量')
    text: str = Field(min_length=1, description='合成内容')
    audio_url: str | None = Field(None, max_length=1000, description='组合成音频地址')


class SongScriptSegment(SchemaBase):
    groups: list[SongScriptGroup] = Field(min_length=1, description='片段内的音频分组')
    audio_url: str | None = Field(None, max_length=1000, description='片段合成音频地址')


class SongSchemaBase(SchemaBase):
    album_id: int | None = Field(None, description='本地专辑 ID')
    title: str = Field(description='歌曲标题')
    subtitle: str | None = Field(None, description='歌曲副标题')
    cover_url: str | None = Field(None, description='歌曲封面地址')
    play_url: str | None = Field(None, description='播放地址')
    artist: str | None = Field(None, description='歌手/主播')
    content: str | None = Field(None, description='歌曲/故事内容')
    script_content: list[SongScriptSegment] = Field(default_factory=list, description='多片段音频合成脚本')
    content_type: ContentType | None = Field(None, description='内容类型：1儿歌 2故事 3哄睡')
    duration: int = Field(default=0, description='时长(秒)')
    track_no: int = Field(default=0, description='曲目序号')
    status: int = Field(default=1, description='状态(0禁用 1启用)')
    remark: str | None = Field(None, description='备注')

    @field_validator('script_content', mode='before')
    @classmethod
    def normalize_script_content(cls, value: Any) -> Any:
        """Keep legacy songs with a NULL JSON column compatible with the API contract."""
        return [] if value is None else value


class CreateSongParam(SongSchemaBase):
    pass


class UpdateSongParam(SchemaBase):
    album_id: int | None = Field(None, description='本地专辑 ID')
    title: str | None = Field(None, description='歌曲标题')
    subtitle: str | None = Field(None, description='歌曲副标题')
    cover_url: str | None = Field(None, description='歌曲封面地址')
    play_url: str | None = Field(None, description='播放地址')
    artist: str | None = Field(None, description='歌手/主播')
    content: str | None = Field(None, description='歌曲/故事内容')
    script_content: list[SongScriptSegment] = Field(default_factory=list, description='多片段音频合成脚本')
    content_type: ContentType | None = Field(None, description='内容类型：1儿歌 2故事 3哄睡')
    duration: int | None = Field(None, description='时长(秒)')
    track_no: int | None = Field(None, description='曲目序号')
    status: int | None = Field(None, description='状态(0禁用 1启用)')
    remark: str | None = Field(None, description='备注')


class GetSongDetail(SongSchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='歌曲 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
