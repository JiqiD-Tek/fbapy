# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : app.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 14:47
"""

from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class AppSchemaBase(SchemaBase):
    """应用基础模型"""

    name: str = Field(description='应用名称')
    package_name: str = Field(description='包名')
    size: int | None = Field(None, description='大小')
    md5: str | None = Field(None, description='MD5')
    version: str | None = Field(None, description='版本')

    icon: str | None = Field(None, description='图标')
    description: str | None = Field(None, description='描述')
    download_url: str | None = Field(None, description='下载地址')
    market_code: str | None = Field(None, description='市场区域编码')
    status: int | None = Field(default=0, description='状态(0禁用 1启用)')
    remark: str | None = Field(None, description='备注')


class CreateAppParam(AppSchemaBase):
    """创建应用参数"""


class UpdateAppParam(AppSchemaBase):
    """更新应用参数"""

    # 可选字段，更新时可以不传
    name: str | None = Field(None, description='应用名称')
    package_name: str | None = Field(None, description='包名')


class DeleteAppParam(SchemaBase):
    """删除应用参数"""

    pks: list[int] = Field(description='应用 ID 列表')


class GetAppDetail(AppSchemaBase):
    """应用详情"""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='应用 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
