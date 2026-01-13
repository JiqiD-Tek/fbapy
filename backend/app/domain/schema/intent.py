# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : intent.py
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
    query: Optional[str] = Field(None, description='原始查询')
    song: Optional[str] = Field(None, description='歌曲名称')
    singer: Optional[str] = Field(None, description='歌手名称')
    album: Optional[str] = Field(None, description='专辑名称')


class ControlParam(ParamBase):
    target: Optional[str] = Field(None, description='目标')
    action: Optional[str] = Field(None, description='动作')
    value: Optional[str] = Field(None, description='值')
