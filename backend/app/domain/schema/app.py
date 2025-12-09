# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : app.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 14:47
"""
from datetime import datetime
from typing import Optional

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class AppSchemaBase(SchemaBase):
    """应用基础模型"""

    name: str = Field(description='应用名称')
    package_name: str = Field(description='包名')
    size: Optional[int] = Field(None, description='大小')
    md5: Optional[str] = Field(None, description='MD5')
    version: Optional[str] = Field(None, description='版本')

    icon: Optional[str] = Field(None, description='图标')
    description: Optional[str] = Field(None, description='描述')
    download_url: Optional[str] = Field(None, description='下载地址')
    status: Optional[int] = Field(default=0, description='状态(0禁用 1启用)')
    remark: Optional[str] = Field(None, description='备注')


class CreateAppParam(AppSchemaBase):
    """创建应用参数"""


class UpdateAppParam(AppSchemaBase):
    """更新应用参数"""

    # 可选字段，更新时可以不传
    name: Optional[str] = Field(None, description='应用名称')
    package_name: Optional[str] = Field(None, description='包名')


class DeleteAppParam(SchemaBase):
    """删除应用参数"""

    pks: list[int] = Field(description='应用 ID 列表')


class GetAppDetail(AppSchemaBase):
    """应用详情"""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='应用 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: Optional[datetime] = Field(None, description='更新时间')
