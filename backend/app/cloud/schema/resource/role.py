# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : role.py
@Author  : OpenAI
@Date    : 2026/07/06
"""

from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class RoleSchemaBase(SchemaBase):
    role_key: str = Field(description='角色唯一标识')
    group_key: str | None = Field(None, description='虚拟角色分组标识')
    name: str | None = Field(None, description='角色名称')
    system_prompt: str | None = Field(None, description='系统提示词')
    avatar_url: str | None = Field(None, description='角色头像地址')
    summary: str | None = Field(None, description='角色简介')
    voice_provider: str | None = Field(None, description='音色提供方')
    voice_id: str | None = Field(None, description='音色 ID')
    voice_type: int | None = Field(None, ge=1, description='音色类型')
    voice_name: str | None = Field(None, description='音色名称')
    voice_language: str | None = Field(None, description='音色语言，如 zh-CN、en-US、zh-TW')
    status: int = Field(default=1, description='状态：0禁用 1启用')
    sort: int = Field(default=0, description='排序值，越小越靠前')
    remark: str | None = Field(None, description='备注')


class CreateRoleParam(RoleSchemaBase):
    pass


class UpdateRoleParam(SchemaBase):
    role_key: str | None = Field(None, description='角色唯一标识')
    group_key: str | None = Field(None, description='虚拟角色分组标识')
    name: str | None = Field(None, description='角色名称')
    system_prompt: str | None = Field(None, description='系统提示词')
    avatar_url: str | None = Field(None, description='角色头像地址')
    summary: str | None = Field(None, description='角色简介')
    voice_provider: str | None = Field(None, description='音色提供方')
    voice_id: str | None = Field(None, description='音色 ID')
    voice_type: int | None = Field(None, ge=1, description='音色类型')
    voice_name: str | None = Field(None, description='音色名称')
    voice_language: str | None = Field(None, description='音色语言，如 zh-CN、en-US、zh-TW')
    status: int | None = Field(None, description='状态：0禁用 1启用')
    sort: int | None = Field(None, description='排序值，越小越靠前')
    remark: str | None = Field(None, description='备注')


class GetRoleDetail(RoleSchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='角色 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetRoleOption(SchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='角色 ID')
    role_key: str = Field(description='角色唯一标识')
    group_key: str | None = Field(None, description='虚拟角色分组标识')
    name: str | None = Field(None, description='角色名称')
    avatar_url: str | None = Field(None, description='角色头像地址')
    summary: str | None = Field(None, description='角色简介')
    voice_name: str | None = Field(None, description='音色名称')
    voice_language: str | None = Field(None, description='音色语言，如 zh-CN、en-US、zh-TW')
