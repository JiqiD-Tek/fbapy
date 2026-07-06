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
    GetRoleDetail,
    GetRoleOption,
    UpdateRoleParam,
)
from backend.app.cloud.service.resource.role_service import cloud_role_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth import DependsDeviceOrJwtAuth
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/enabled', summary='获取启用角色列表', dependencies=[DependsDeviceOrJwtAuth])
async def get_enabled_roles(
    db: CurrentSession,
    group_key: Annotated[str | None, Query(description='虚拟角色分组标识')] = None,
) -> ResponseSchemaModel[list[GetRoleOption]]:
    roles = await cloud_role_service.get_enabled_role_list(db=db, group_key=group_key)
    data = [GetRoleOption.model_validate(role) for role in roles]
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取角色详情', dependencies=[DependsJwtAuth])
async def get_role(
    db: CurrentSession,
    pk: Annotated[int, Path(description='角色 ID')],
) -> ResponseSchemaModel[GetRoleDetail]:
    role = await cloud_role_service.get_role(db=db, pk=pk)
    return response_base.success(data=GetRoleDetail.model_validate(role))


@router.get('', summary='分页获取角色列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_role_paginated(
    db: CurrentSession,
    role_key: Annotated[str | None, Query(description='角色唯一标识')] = None,
    group_key: Annotated[str | None, Query(description='虚拟角色分组标识')] = None,
    name: Annotated[str | None, Query(description='角色名称')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetRoleDetail]]:
    page_data = await cloud_role_service.get_role_list(
        db=db,
        role_key=role_key,
        group_key=group_key,
        name=name,
        status=status,
    )
    page_data['items'] = [GetRoleDetail.model_validate(item) for item in page_data['items']]
    return response_base.success(data=page_data)


@router.post('', summary='创建角色', dependencies=[DependsJwtAuth])
async def create_role(
    db: CurrentSessionTransaction,
    obj: CreateRoleParam,
) -> ResponseSchemaModel[GetRoleDetail]:
    role = await cloud_role_service.create_role(db=db, obj=obj)
    return response_base.success(data=GetRoleDetail.model_validate(role))


@router.put('/{pk}', summary='更新角色', dependencies=[DependsJwtAuth])
async def update_role(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='角色 ID')],
    obj: UpdateRoleParam,
) -> ResponseModel:
    count = await cloud_role_service.update_role(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除角色', dependencies=[DependsJwtAuth])
async def delete_role(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='角色 ID')],
) -> ResponseModel:
    count = await cloud_role_service.delete_role(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
