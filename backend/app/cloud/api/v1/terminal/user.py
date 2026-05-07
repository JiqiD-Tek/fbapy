from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.cloud.schema.baby import GetBabyDetail
from backend.app.cloud.schema.device.device import GetDeviceDetail
from backend.app.cloud.schema.user import GetUserInfoDetail, UserDeviceParam
from backend.app.cloud.service.baby_service import baby_service
from backend.app.cloud.service.user_service import user_service
from backend.common.exception import errors
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth, DependsSuperUser
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/me', summary='获取当前用户信息', dependencies=[DependsJwtAuth])
async def get_cloud_user(request: Request) -> ResponseSchemaModel[GetUserInfoDetail]:
    data = request.user.model_dump()
    return response_base.success(data=data)


@router.get('', summary='分页获取用户列表', dependencies=[DependsSuperUser, DependsPagination])
async def get_cloud_users_paginated(
        request: Request,
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


@router.get('/me/babies', summary='获取当前用户所有宝宝', dependencies=[DependsJwtAuth])
async def get_cloud_user_babies(request: Request, db: CurrentSession) -> ResponseSchemaModel[list[GetBabyDetail]]:
    data = await baby_service.get_user_babies(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.get('/me/devices', summary='获取用户所有设备', dependencies=[DependsJwtAuth])
async def get_cloud_user_devices(
        request: Request,
        db: CurrentSession,
) -> ResponseSchemaModel[list[GetDeviceDetail]]:
    data = await user_service.get_devices(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.post('/bind', summary='设备绑定', dependencies=[DependsJwtAuth])
async def bind_device(
        request: Request,
        db: CurrentSessionTransaction,
        obj: UserDeviceParam,
) -> ResponseModel:
    if obj.user_id != request.user.id:
        raise errors.RequestError(msg='无权操作其他用户')

    await user_service.bind_device(db=db, obj=obj)
    return response_base.success()


@router.post('/unbind', summary='设备解绑', dependencies=[DependsJwtAuth])
async def unbind_device(
        request: Request,
        db: CurrentSessionTransaction,
        obj: UserDeviceParam,
) -> ResponseModel:
    if obj.user_id != request.user.id:
        raise errors.RequestError(msg='无权操作其他用户')

    await user_service.unbind_device(db=db, obj=obj)
    return response_base.success()
