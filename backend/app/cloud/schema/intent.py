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
