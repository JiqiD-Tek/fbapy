from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.cloud.schema.device.device import GetDeviceDetail
from backend.app.cloud.schema.user import (
    GetUserInfoDetail,
    UserDeviceParam,
)
from backend.app.cloud.service.user_service import user_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth import DependsDeviceAuth
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/me', summary='获取当前用户信息', dependencies=[DependsDeviceAuth, DependsJwtAuth])
async def get_k10_user(request: Request) -> ResponseSchemaModel[GetUserInfoDetail]:
    data = request.user.model_dump()
    return response_base.success(data=data)


@router.get('', summary='分页获取用户列表', dependencies=[DependsDeviceAuth, DependsJwtAuth, DependsPagination])
async def get_users_paginated(
    db: CurrentSession,
    username: Annotated[str | None, Query(description='用户名')] = None,
    nickname: Annotated[str | None, Query(description='昵称')] = None,
    phone: Annotated[str | None, Query(description='手机号')] = None,
    email: Annotated[str | None, Query(description='邮箱')] = None,
) -> ResponseSchemaModel[PageData[GetUserInfoDetail]]:
    page_data = await user_service.get_list(
        db=db,
        username=username,
        nickname=nickname,
        phone=phone,
        email=email,
    )
    return response_base.success(data=page_data)


@router.get('/{pk}/devices', summary='获取用户所有设备', dependencies=[DependsDeviceAuth, DependsJwtAuth])
async def get_user_devices(
    db: CurrentSession, pk: Annotated[int, Path(description='用户 ID')]
) -> ResponseSchemaModel[list[GetDeviceDetail]]:
    data = await user_service.get_devices(db=db, pk=pk)
    return response_base.success(data=data)


@router.post('/bind', summary='设备绑定', dependencies=[DependsDeviceAuth, DependsJwtAuth])
async def bind_device(
    db: CurrentSessionTransaction,
    obj: UserDeviceParam,
) -> ResponseModel:
    """设备绑定"""
    await user_service.bind_device(db=db, obj=obj)
    return response_base.success()


@router.post('/unbind', summary='设备解绑', dependencies=[DependsDeviceAuth, DependsJwtAuth])
async def unbind_device(
    db: CurrentSessionTransaction,
    obj: UserDeviceParam,
) -> ResponseModel:
    """设备解绑"""
    await user_service.unbind_device(db=db, obj=obj)
    return response_base.success()
