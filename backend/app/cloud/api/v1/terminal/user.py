from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.cloud.schema.device.device import GetDeviceDetail
from backend.app.cloud.schema.user import DeviceAuthParam, GetUserInfoDetail, UserDeviceParam
from backend.app.cloud.service.device_service import device_service
from backend.app.cloud.service.user_service import user_service
from backend.common.exception import errors
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth import device_or_jwt_auth_verify
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/me', summary='获取当前用户信息', dependencies=[DependsJwtAuth])
async def get_k10_user(request: Request) -> ResponseSchemaModel[GetUserInfoDetail]:
    data = request.user.model_dump()
    return response_base.success(data=data)


@router.get('', summary='分页获取用户列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_terminal_users_paginated(
    db: CurrentSession,
    unionid: Annotated[str | None, Query(description='微信 UnionID')] = None,
    username: Annotated[str | None, Query(description='用户名')] = None,
    nickname: Annotated[str | None, Query(description='昵称')] = None,
    phone: Annotated[str | None, Query(description='手机号')] = None,
    email: Annotated[str | None, Query(description='邮箱')] = None,
) -> ResponseSchemaModel[PageData[GetUserInfoDetail]]:
    page_data = await user_service.get_list(
        db=db,
        unionid=unionid,
        username=username,
        nickname=nickname,
        phone=phone,
        email=email,
    )
    return response_base.success(data=page_data)


@router.get('/{pk}/devices', summary='获取用户所有设备', dependencies=[DependsJwtAuth])
async def get_user_devices(
    db: CurrentSession, pk: Annotated[int, Path(description='用户 ID')]
) -> ResponseSchemaModel[list[GetDeviceDetail]]:
    data = await user_service.get_devices(db=db, pk=pk)
    return response_base.success(data=data)


@router.post('/bind', summary='设备绑定')
async def bind_device(
    db: CurrentSessionTransaction,
    obj: UserDeviceParam,
    auth_ctx: Annotated[Any, Depends(device_or_jwt_auth_verify)],
) -> ResponseModel:
    if isinstance(auth_ctx, DeviceAuthParam):
        current_device = await device_service.get_by_did(db=db, did=auth_ctx.did)
        if current_device.id != obj.device_id:
            raise errors.RequestError(msg='无权操作其他设备')

    await user_service.bind_device(db=db, obj=obj)
    return response_base.success()


@router.post('/unbind', summary='设备解绑')
async def unbind_device(
    db: CurrentSessionTransaction,
    obj: UserDeviceParam,
    auth_ctx: Annotated[Any, Depends(device_or_jwt_auth_verify)],
) -> ResponseModel:
    if isinstance(auth_ctx, DeviceAuthParam):
        current_device = await device_service.get_by_did(db=db, did=auth_ctx.did)
        if current_device.id != obj.device_id:
            raise errors.RequestError(msg='无权操作其他设备')

    await user_service.unbind_device(db=db, obj=obj)
    return response_base.success()
