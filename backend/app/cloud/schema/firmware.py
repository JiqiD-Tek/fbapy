# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : firmware.py
@Author  : OpenAI
@Date    : 2026/03/26
"""

from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class FirmwareSchemaBase(SchemaBase):
    """固件基础模型"""

    name: str = Field(description='固件名称')
    version: str = Field(description='固件版本')
    version_code: int = Field(description='版本代码')
    size: int = Field(description='固件大小')
    md5: str = Field(description='固件 MD5')
    download_url: str = Field(description='固件下载地址')

    download_count: int = Field(default=0, description='下载次数')
    description: str | None = Field(None, description='固件描述')
    min_version: str | None = Field(None, description='最低兼容版本')
    max_version: str | None = Field(None, description='最高兼容版本')
    device_model: str | None = Field(None, description='适配设备型号')
    is_latest: bool = Field(default=False, description='是否为最新版本')
    is_force: bool = Field(default=False, description='是否强制更新')
    status: int = Field(default=0, description='固件状态(0禁用 1启用)')
    remark: str | None = Field(None, description='备注')


class CreateFirmwareParam(FirmwareSchemaBase):
    """创建固件参数"""


class UpdateFirmwareParam(SchemaBase):
    """更新固件参数"""

    name: str | None = Field(None, description='固件名称')
    version: str | None = Field(None, description='固件版本')
    version_code: int | None = Field(None, description='版本代码')
    size: int | None = Field(None, description='固件大小')
    md5: str | None = Field(None, description='固件 MD5')
    download_url: str | None = Field(None, description='固件下载地址')

    download_count: int | None = Field(None, description='下载次数')
    description: str | None = Field(None, description='固件描述')
    min_version: str | None = Field(None, description='最低兼容版本')
    max_version: str | None = Field(None, description='最高兼容版本')
    device_model: str | None = Field(None, description='适配设备型号')
    is_latest: bool | None = Field(None, description='是否为最新版本')
    is_force: bool | None = Field(None, description='是否强制更新')
    status: int | None = Field(None, description='固件状态(0禁用 1启用)')
    remark: str | None = Field(None, description='备注')


class DeleteFirmwareParam(SchemaBase):
    """删除固件参数"""

    pks: list[int] = Field(description='固件 ID 列表')


class GetFirmwareDetail(FirmwareSchemaBase):
    """固件详情"""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='固件 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
