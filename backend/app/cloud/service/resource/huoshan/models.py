# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : models.py
@Author  : OpenAI
@Date    : 2026/04/13
"""

from __future__ import annotations

from dataclasses import dataclass

HUOSHAN_OPENAPI_CONTENT_TYPE = 'application/json; charset=utf-8'
HUOSHAN_TTS_JSON_CONTENT_TYPE = 'application/json; charset=utf-8'


@dataclass(frozen=True)
class HuoshanOpenAPIConfig:
    access_key: str
    secret_key: str
    host: str
    region: str
    service: str
    version: str
    timeout: float

    @property
    def base_url(self) -> str:
        return f'https://{self.host}'


@dataclass(frozen=True)
class HuoshanLongTextTTSConfig:
    app_id: str
    access_key: str
    resource_id: str
    query_resource_id: str
    submit_url: str
    query_url: str
    timeout: float
