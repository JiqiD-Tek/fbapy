# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : app.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:20
"""

from typing import Annotated
from fastapi import APIRouter, Query, Path

from backend.app.domain.service.device import device_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseSchemaModel, ResponseModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

from backend.app.domain.schema.device import (
    GetDeviceDetail,
    CreateDeviceParam,
    UpdateDeviceParam,
    DeleteDeviceParam,
)

router = APIRouter()


# =============================
# 获取单个设备
# =============================
@router.get(
    "/{pk}",
    summary="获取设备详情",
    dependencies=[DependsJwtAuth],
)
async def get_device(
        db: CurrentSession,
        pk: Annotated[int, Path(description="设备 ID")]
) -> ResponseSchemaModel[GetDeviceDetail]:
    data = device_service.get(db=db, pk=pk)
    return response_base.success(data=data)


# =============================
# 分页列表
# =============================
@router.get(
    "",
    summary="分页获取设备列表",
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_device_paginated(
        db: CurrentSession,
        did: Annotated[str | None, Query(description='设备编码')] = None,
        sn: Annotated[str | None, Query(description='设备序列号')] = None,
        mac: Annotated[str | None, Query(description='MAC地址')] = None,
        model: Annotated[str | None, Query(description='设备型号')] = None,
        user_id: Annotated[int | None, Query(description='用户ID')] = None,
) -> ResponseSchemaModel[PageData[GetDeviceDetail]]:
    page_data = await device_service.get_list(
        db=db,
        did=did,
        sn=sn,
        mac=mac,
        model=model,
        user_id=user_id,
    )
    return response_base.success(data=page_data)


# =============================
# 创建设备
# =============================
@router.post(
    "",
    summary="创建设备",
    dependencies=[DependsJwtAuth],
)
async def create_device(
        db: CurrentSessionTransaction,
        obj: CreateDeviceParam,
) -> ResponseSchemaModel[GetDeviceDetail]:
    device = await device_service.create(db=db, obj=obj)
    return response_base.success(data=device)


# =============================
# 更新设备
# =============================
@router.put(
    "/{pk}",
    summary="更新设备",
    dependencies=[DependsJwtAuth],
)
async def update_device(
        db: CurrentSessionTransaction,
        pk: Annotated[int, Path(description="设备 ID")],
        obj: UpdateDeviceParam,
) -> ResponseModel:
    count = await device_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# =============================
# 删除设备
# =============================
@router.delete(
    "/{pk}",
    summary="删除设备",
    dependencies=[DependsJwtAuth],
)
async def delete_device(
        db: CurrentSessionTransaction,
        obj: DeleteDeviceParam,
) -> ResponseModel:
    count = await device_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
