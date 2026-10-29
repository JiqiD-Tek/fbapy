# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : app.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:20
"""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.cloud.schema.app import CreateAppParam, GetAppDetail, UpdateAppParam
from backend.app.cloud.service.app_service import app_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth import DependsDeviceAuth, DependsDeviceOrJwtAuth
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/upgrade',
    summary='获取可升级应用版本',
    dependencies=[DependsDeviceAuth],
)
async def get_upgrade_app(
    db: CurrentSession,
    package_name: Annotated[str, Query(description='应用包名')],
    version_code: Annotated[int, Query(ge=0, description='当前应用版本代码')],
    market_code: Annotated[str | None, Query(description='市场区域编码')] = None,
) -> ResponseSchemaModel[GetAppDetail | None]:
    data = await app_service.get_upgrade(
        db=db,
        package_name=package_name,
        market_code=market_code,
        version_code=version_code,
    )
    return response_base.success(data=data)


@router.get(
    '/{pk}',
    summary='获取应用详情',
    dependencies=[DependsDeviceOrJwtAuth],
)
async def get_app(
    db: CurrentSession, pk: Annotated[int, Path(description='应用 ID')]
) -> ResponseSchemaModel[GetAppDetail]:
    data = await app_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='分页获取应用列表',
    dependencies=[DependsDeviceOrJwtAuth, DependsPagination],
)
async def get_app_paginated(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='应用名称')] = None,
    package_name: Annotated[str | None, Query(description='包名')] = None,
    market_code: Annotated[
        str | None,
        Query(description='市场区域编码；不传查询全部，传空值查询通用版本（数据库 NULL）'),
    ] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetAppDetail]]:
    page_data = await app_service.get_list(
        db=db,
        name=name,
        package_name=package_name,
        market_code=market_code,
        status=status,
    )
    return response_base.success(data=page_data)


@router.post(
    '',
    summary='创建应用',
    dependencies=[DependsJwtAuth],
)
async def create_app(
    db: CurrentSessionTransaction,
    obj: CreateAppParam,
) -> ResponseSchemaModel[GetAppDetail]:
    app = await app_service.create(db=db, obj=obj)
    return response_base.success(data=app)


@router.put(
    '/{pk}',
    summary='更新应用',
    dependencies=[DependsJwtAuth],
)
async def update_app(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='应用 ID')],
    obj: UpdateAppParam,
) -> ResponseModel:
    count = await app_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/{pk}',
    summary='删除应用',
    dependencies=[DependsJwtAuth],
)
async def delete_app(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='应用 ID')]
) -> ResponseModel:
    count = await app_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
