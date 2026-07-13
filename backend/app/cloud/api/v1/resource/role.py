# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : role.py
@Author  : OpenAI
@Date    : 2026/07/06
"""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.cloud.schema.resource.role import (
    CreateRoleParam,
    GenerateRoleSystemPromptParam,
    GenerateRoleSystemPromptResult,
    GetRoleDetail,
    UpdateRoleParam,
)
from backend.app.cloud.service.resource.role_service import cloud_role_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取剧本角色详情', dependencies=[DependsJwtAuth])
async def get_role(
    db: CurrentSession,
    pk: Annotated[int, Path(description='剧本角色 ID')],
) -> ResponseSchemaModel[GetRoleDetail]:
    role = await cloud_role_service.get_role(db=db, pk=pk)
    return response_base.success(data=GetRoleDetail.model_validate(role))


@router.get('', summary='分页获取剧本角色列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_role_paginated(
    db: CurrentSession,
    group_key: Annotated[str | None, Query(description='剧本角色分组标识')] = None,
    name: Annotated[str | None, Query(description='角色名称')] = None,
    voice_language: Annotated[str | None, Query(description='音色语言，如 zh-CN、en-US、zh-TW')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetRoleDetail]]:
    page_data = await cloud_role_service.get_role_list(
        db=db,
        group_key=group_key,
        name=name,
        voice_language=voice_language,
        status=status,
    )
    page_data['items'] = [GetRoleDetail.model_validate(item) for item in page_data['items']]
    return response_base.success(data=page_data)


@router.post('/system-prompt', summary='生成剧本角色系统提示词', dependencies=[DependsJwtAuth])
async def generate_role_system_prompt(
    obj: GenerateRoleSystemPromptParam,
) -> ResponseSchemaModel[GenerateRoleSystemPromptResult]:
    data = await cloud_role_service.generate_system_prompt(obj)
    return response_base.success(data=data)


@router.post('', summary='创建剧本角色', dependencies=[DependsJwtAuth])
async def create_role(
    db: CurrentSessionTransaction,
    obj: CreateRoleParam,
) -> ResponseSchemaModel[GetRoleDetail]:
    role = await cloud_role_service.create_role(db=db, obj=obj)
    return response_base.success(data=GetRoleDetail.model_validate(role))


@router.put('/{pk}', summary='更新剧本角色', dependencies=[DependsJwtAuth])
async def update_role(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='剧本角色 ID')],
    obj: UpdateRoleParam,
) -> ResponseModel:
    count = await cloud_role_service.update_role(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除剧本角色', dependencies=[DependsJwtAuth])
async def delete_role(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='剧本角色 ID')],
) -> ResponseModel:
    count = await cloud_role_service.delete_role(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
