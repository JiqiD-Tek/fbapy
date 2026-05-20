# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : app.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:20
"""

from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.cloud.schema.baby import DeviceBabyParam, GetBabyDetail
from backend.app.cloud.schema.device.device import GetDeviceDetail, UpdateDeviceParam
from backend.app.cloud.schema.device.device_state import GetDeviceStateDetail
from backend.app.cloud.schema.token import MiniProvisionBindParam, MiniProvisionStatusDetail
from backend.app.cloud.schema.user import DeviceAuthParam
from backend.app.cloud.service.auth_service import auth_service
from backend.app.cloud.service.baby_service import baby_service
from backend.app.cloud.service.device_service import device_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth import DependsDeviceAuth
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.post('/bind/token', summary='设备通过配网 token 绑定用户')
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


@router.post('/baby/bind', summary='绑定设备宝宝关系', dependencies=[DependsJwtAuth])
async def bind_device_baby(
        request: Request,
        db: CurrentSessionTransaction,
        obj: DeviceBabyParam,
) -> ResponseModel:
    await baby_service.bind_device_baby(db=db, user_id=request.user.id, obj=obj)
    return response_base.success()


@router.post('/baby/unbind', summary='解绑设备宝宝关系', dependencies=[DependsJwtAuth])
async def unbind_device_baby(
        request: Request,
        db: CurrentSessionTransaction,
        obj: DeviceBabyParam,
) -> ResponseModel:
    await baby_service.unbind_device_baby(db=db, user_id=request.user.id, obj=obj)
    return response_base.success()


@router.get('/{pk}', summary='获取设备详情', dependencies=[DependsJwtAuth])
async def get_device(
        request: Request,
        db: CurrentSession,
        pk: Annotated[int, Path(description='设备 ID')],
) -> ResponseSchemaModel[GetDeviceDetail]:
    data = await device_service.get(db=db, user_id=request.user.id, pk=pk)
    return response_base.success(data=data)


@router.get('/{pk}/state', summary='获取设备当前状态', dependencies=[DependsJwtAuth])
async def get_device_state(
        request: Request,
        db: CurrentSession,
        pk: Annotated[int, Path(description='设备 ID')],
) -> ResponseSchemaModel[GetDeviceStateDetail | None]:
    data = await device_service.get_state(db=db, user_id=request.user.id, pk=pk)
    if data is None:
        return response_base.success(data=None)
    return response_base.success(data=GetDeviceStateDetail.model_validate(data))


@router.get('/{pk}/babies', summary='获取设备绑定的宝宝列表', dependencies=[DependsJwtAuth])
async def get_device_babies(
        request: Request,
        db: CurrentSession,
        pk: Annotated[int, Path(description='设备 ID')],
) -> ResponseSchemaModel[list[GetBabyDetail]]:
    data = await baby_service.get_device_babies(db=db, user_id=request.user.id, device_id=pk)
    return response_base.success(data=data)


@router.get('', summary='分页获取设备列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_device_paginated(
        request: Request,
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


@router.put('/{pk}', summary='更新设备', dependencies=[DependsJwtAuth])
async def update_device(
        request: Request,
        db: CurrentSessionTransaction,
        pk: Annotated[int, Path(description='设备 ID')],
        obj: UpdateDeviceParam,
) -> ResponseModel:
    count = await device_service.update(db=db, user_id=request.user.id, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除设备', dependencies=[DependsJwtAuth])
async def delete_device(
        request: Request,
        db: CurrentSessionTransaction,
        pk: Annotated[int, Path(description='设备 ID')],
) -> ResponseModel:
    count = await device_service.delete(db=db, user_id=request.user.id, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
