# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : app.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:20
"""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.cloud.schema.device.device import (
    GetDeviceDetail,
    UpdateDeviceParam,
)
from backend.app.cloud.schema.token import MiniProvisionBindParam, MiniProvisionStatusDetail
from backend.app.cloud.schema.user import DeviceAuthParam
from backend.app.cloud.service.auth_service import auth_service
from backend.app.cloud.service.device_service import device_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth import DependsDeviceAuth
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


# =============================
# 设备通过配网 token 绑定用户
# =============================
@router.post(
    '/bind/token',
    summary='设备通过配网 token 绑定用户',
)
async def bind_device_by_token(
    db: CurrentSessionTransaction,
    obj: MiniProvisionBindParam,
    device: DeviceAuthParam = DependsDeviceAuth,
) -> ResponseSchemaModel[MiniProvisionStatusDetail]:
    data = await auth_service.bind_device_by_mini_provision_token(
        db=db,
        device=device,
        token=obj.token,
    )
    return response_base.success(data=data)


# =============================
# 获取单个设备
# =============================
@router.get(
    '/{pk}',
    summary='获取设备详情',
    dependencies=[DependsJwtAuth],
)
async def get_device(
    db: CurrentSession, pk: Annotated[int, Path(description='设备 ID')]
) -> ResponseSchemaModel[GetDeviceDetail]:
    data = await device_service.get(db=db, pk=pk)
    return response_base.success(data=data)


# =============================
# 分页列表
# =============================
@router.get(
    '',
    summary='分页获取设备列表',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_device_paginated(
    db: CurrentSession,
    did: Annotated[str | None, Query(description='设备编码')] = None,
    sn: Annotated[str | None, Query(description='设备序列号')] = None,
    mac: Annotated[str | None, Query(description='MAC地址')] = None,
    model: Annotated[str | None, Query(description='设备型号')] = None,
) -> ResponseSchemaModel[PageData[GetDeviceDetail]]:
    page_data = await device_service.get_list(
        db=db,
        did=did,
        sn=sn,
        mac=mac,
        model=model,
    )
    return response_base.success(data=page_data)


# =============================
# 更新设备
# =============================
@router.put(
    '/{pk}',
    summary='更新设备',
    dependencies=[DependsJwtAuth],
)
async def update_device(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='设备 ID')],
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
    '/{pk}',
    summary='删除设备',
    dependencies=[DependsJwtAuth],
)
async def delete_device(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='设备 ID')]
) -> ResponseModel:
    count = await device_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
