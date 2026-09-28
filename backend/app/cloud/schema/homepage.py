# -*- coding: UTF-8 -*-
"""首页配置请求和响应模型。"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase


HomepageItem = Any


class HomepageType(str, Enum):
    """首页配置类型。"""

    banner = 'banner'
    newest = 'newest'
    featured = 'featured'


class UpdateHomepageParam(SchemaBase):
    """更新首页配置参数。"""

    banner: list[HomepageItem] = Field(default_factory=list, description='顶部轮播配置数组')
    newest: list[HomepageItem] = Field(default_factory=list, description='新品轮播配置数组')
    featured: list[HomepageItem] = Field(default_factory=list, description='更多精选配置数组')


class HomepageDetail(UpdateHomepageParam):
    """首页配置详情。"""
