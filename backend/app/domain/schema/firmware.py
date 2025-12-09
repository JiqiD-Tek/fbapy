# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : firmware.py
@Author  : guhua@jiqid.com
@Date    : 2025/12/04
"""
from datetime import datetime
from typing import Optional

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class FirmwareSchemaBase(SchemaBase):
    """固件基础模型"""

    name: str = Field(description='固件名称')
    version: str = Field(description='固件版本')
    version_code: int = Field(description='版本代码')
    size: int = Field(description='固件大小')
    md5: str = Field(description='固件MD5')
    download_url: str = Field(description='固件下载地址')

    download_count: Optional[int] = Field(default=0, description='下载次数')
    description: Optional[str] = Field(None, description='固件描述')
    min_version: Optional[str] = Field(None, description='最低兼容版本')
    max_version: Optional[str] = Field(None, description='最高兼容版本')
    device_model: Optional[str] = Field(None, description='适用设备型号')
    is_latest: Optional[bool] = Field(default=False, description='是否为最新版本')
    is_force: Optional[bool] = Field(default=False, description='是否强制更新')
    status: Optional[int] = Field(default=0, description='固件状态(0禁用 1启用)')
    remark: Optional[str] = Field(None, description='备注')


class CreateFirmwareParam(FirmwareSchemaBase):
    """创建固件参数"""


class UpdateFirmwareParam(FirmwareSchemaBase):
    """更新固件参数"""

    # 可选字段，更新时可以不传
    name: Optional[str] = Field(None, description='固件名称')
    version: Optional[str] = Field(None, description='固件版本')
    version_code: Optional[int] = Field(None, description='版本代码')
    size: Optional[int] = Field(None, description='固件大小')
    md5: Optional[str] = Field(None, description='固件MD5')
    download_url: Optional[str] = Field(None, description='固件下载地址')


class DeleteFirmwareParam(SchemaBase):
    """删除固件参数"""

    pks: list[int] = Field(description='固件 ID 列表')


class GetFirmwareDetail(FirmwareSchemaBase):
    """固件详情"""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='固件 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: Optional[datetime] = Field(None, description='更新时间')
