"""小雅开放平台公共类型与基础常量。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

RequestScalar: TypeAlias = str | int | float | bool | None
RequestValue: TypeAlias = RequestScalar | dict[str, Any] | list[Any] | tuple[Any, ...]
RequestParams: TypeAlias = dict[str, RequestValue]
JSONResponse: TypeAlias = dict[str, Any] | list[Any]

DEFAULT_BASE_URL = 'https://api.ximalaya.com/ximalayaos-openapi-xm'
FORM_CONTENT_TYPE = 'application/x-www-form-urlencoded; charset=UTF-8'


@dataclass(frozen=True, slots=True)
class XimalayaEndpoint:
    group: str
    name: str
    path: str
    method: Literal['GET', 'POST']
    section: str
    description: str


@dataclass(slots=True)
class XimalayaClientConfig:
    app_key: str
    app_secret: str
    sn: str
    device_id: str
    client_os_type: int = 3
    device_id_type: str = 'UUID'
    version: str | None = None
    base_url: str = DEFAULT_BASE_URL


__all__ = [
    'DEFAULT_BASE_URL',
    'FORM_CONTENT_TYPE',
    'JSONResponse',
    'RequestParams',
    'RequestScalar',
    'RequestValue',
    'XimalayaClientConfig',
    'XimalayaEndpoint',
]
