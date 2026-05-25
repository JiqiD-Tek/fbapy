# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : tool.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 14:47
"""

from pydantic import Field

from backend.common.schema import SchemaBase


class ParamBase(SchemaBase):
    did: str = Field(description='设备did')


class WeatherParam(ParamBase):
    city: str | None = Field(None, description='城市')
    ip: str | None = Field(None, description='IP地址')


class DeviceToolParam(ParamBase):
    model: str = Field(description='设备型号')


class MusicToolParam(DeviceToolParam):
    action: str = Field(description='操作')
    value: str | None = Field(None, description='值')
    song: str | None = Field(None, description='歌曲名称')
    artist: str | None = Field(None, description='歌手名称')
    playlist: str | None = Field(None, description='专辑名称')
    platform: str | None = Field(None, description='播放平台')
    play_url: str | None = Field(None, description='音频地址')


class ControlToolParam(DeviceToolParam):
    action: str = Field(description='动作')
    target: str = Field(description='目标')
    value: str | None = Field(None, description='值')


class AlarmToolParam(DeviceToolParam):
    action: str = Field(description='操作')
    target_time: str | None = Field(None, description='时间')
    message: str | None = Field(None, description='消息')
