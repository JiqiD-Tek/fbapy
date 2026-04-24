# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : ximalaya.py
@Author  : OpenAI
@Date    : 2026/03/25
"""

from __future__ import annotations

from pydantic import Field

from backend.common.schema import SchemaBase


class XimalayaRequestBase(SchemaBase):
    """小雅接口请求公共参数。"""

    did: str = Field(description='设备唯一标识，用于服务端生成签名')


class XimalayaRecommendedParam(XimalayaRequestBase):
    """推荐接口仅依赖公共参数。"""


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
