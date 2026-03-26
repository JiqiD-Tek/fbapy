# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : ximalaya.py
@Author  : OpenAI
@Date    : 2026/03/25
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, SecretStr

from backend.app.cloud.service.resource.ximalaya.models import DEFAULT_BASE_URL, XimalayaClientConfig
from backend.common.schema import SchemaBase


class XimalayaConfigParam(SchemaBase):
    """小雅开放平台调用配置。"""

    app_key: str = Field(description='开放平台 app_key')
    app_secret: SecretStr = Field(description='开放平台 app_secret')
    sn: str = Field(description='产品 sn')
    device_id: str = Field(description='设备唯一标识')
    client_os_type: int = Field(3, description='客户端系统类型，默认 Web/API 接入')
    device_id_type: str = Field('UUID', description='设备 ID 类型')
    version: str | None = Field(None, description='版本号')
    base_url: str = Field(DEFAULT_BASE_URL, description='开放平台基础地址')

    def to_client_config(self) -> XimalayaClientConfig:
        return XimalayaClientConfig(
            app_key=self.app_key,
            app_secret=self.app_secret.get_secret_value(),
            sn=self.sn,
            device_id=self.device_id,
            client_os_type=self.client_os_type,
            device_id_type=self.device_id_type,
            version=self.version,
            base_url=self.base_url,
        )


class XimalayaRequestBase(SchemaBase):
    """小雅接口请求公共参数。"""

    config: XimalayaConfigParam = Field(description='开放平台调用配置')
    nonce: str | None = Field(None, description='可选，自定义随机串')
    timestamp: int | None = Field(None, description='可选，自定义毫秒时间戳')

    def build_request_options(self) -> dict[str, Any]:
        return {'nonce': self.nonce, 'timestamp': self.timestamp}

    def build_business_params(self, *, exclude: set[str] | None = None) -> dict[str, Any]:
        excluded = {'config', 'nonce', 'timestamp'}
        if exclude:
            excluded |= exclude
        return self.model_dump(exclude_none=True, exclude=excluded)


class XimalayaEndpointInvokeParam(XimalayaRequestBase):
    endpoint_key: str = Field(description='注册表中的接口 key，如 on_demand.list_categories')
    params: dict[str, Any] | None = Field(None, description='业务参数')


class XimalayaPathInvokeParam(XimalayaRequestBase):
    method: Literal['GET', 'POST'] = Field('GET', description='请求方法')
    path: str = Field(description='开放平台接口路径')
    params: dict[str, Any] | None = Field(None, description='业务参数')


class XimalayaListCategoriesParam(XimalayaRequestBase):
    """分类列表仅依赖公共参数。"""


class XimalayaListTagsParam(XimalayaRequestBase):
    category_id: int = Field(description='分类 ID')
    type: int = Field(description='0-专辑标签，1-声音标签')


class XimalayaListAlbumsParam(XimalayaRequestBase):
    category_id: int = Field(description='分类 ID')
    calc_dimension: int = Field(description='排序维度：1-最火，2-最新，3-最多播放')
    tag_name: str | None = Field(None, description='标签名称')
    page: int | None = Field(None, description='页码，从 1 开始')
    count: int | None = Field(None, description='每页条数')
    contains_paid: bool | None = Field(None, description='是否包含付费内容')


class XimalayaBrowseAlbumParam(XimalayaRequestBase):
    album_id: int = Field(description='专辑 ID')
    sort: str | None = Field(None, description='排序方式')
    page: int | None = Field(None, description='页码，从 1 开始')
    count: int | None = Field(None, description='每页条数')
    exclude_fields: str | None = Field(None, description='屏蔽字段，多个英文逗号分隔')


class XimalayaSearchAlbumsParam(XimalayaRequestBase):
    q: str = Field(description='搜索关键词')
    category_id: int | None = Field(None, description='分类 ID')
    page: int | None = Field(None, description='页码，从 1 开始')
    count: int | None = Field(None, description='每页条数')
    calc_dimension: int | None = Field(None, description='排序维度')
    contains_paid: bool | None = Field(None, description='是否包含付费内容')


class XimalayaSearchTracksParam(XimalayaRequestBase):
    q: str = Field(description='搜索关键词')
    category_id: int | None = Field(None, description='分类 ID')
    page: int | None = Field(None, description='页码，从 1 开始')
    count: int | None = Field(None, description='每页条数')


class XimalayaTrackPlayInfoParam(XimalayaRequestBase):
    ids: list[int] = Field(description='声音 ID 列表')

    def build_ids_param(self) -> dict[str, str]:
        return {'ids': ','.join(str(item) for item in self.ids)}
