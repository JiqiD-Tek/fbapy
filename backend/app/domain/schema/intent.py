# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : function.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 14:47
"""
from typing import Optional

from pydantic import Field

from backend.common.schema import SchemaBase


class ParamBase(SchemaBase):
    did: str = Field(description='设备did')


class WeatherParam(ParamBase):
    city: Optional[str] = Field(None, description='城市')
    ip: Optional[str] = Field(None, description='IP地址')


class MusicParam(ParamBase):
    # play | pause | stop | next | prev | volume_up | volume_down | volume_set
    action: Optional[str] = Field(None, description='操作')

    value: Optional[str] = Field(None, description='值')
    song: Optional[str] = Field(None, description='歌曲名称')
    artist: Optional[str] = Field(None, description='歌手名称')
    playlist: Optional[str] = Field(None, description='专辑名称')
    platform: Optional[str] = Field(None, description='播放平台')


class AlarmParam(ParamBase):
    action: Optional[str] = Field(None, description='操作')
    target_time: Optional[str] = Field(None, description='时间')
    message: Optional[str] = Field(None, description='消息')


class ControlParam(ParamBase):
    target: Optional[str] = Field(None, description='目标')
    action: Optional[str] = Field(None, description='动作')
    value: Optional[str] = Field(None, description='值')
