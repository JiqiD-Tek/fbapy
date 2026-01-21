from typing import Annotated

from fastapi import APIRouter, Path, Request

from backend.app.domain.schema.device import GetDeviceDetail
from backend.app.domain.schema.user import (
    GetUserInfoDetail, UserDeviceParam,
)
from backend.app.domain.service.user_service import user_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base, ResponseModel
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/me', summary='获取当前用户信息', dependencies=[DependsJwtAuth])
async def get_k10_user(request: Request) -> ResponseSchemaModel[GetUserInfoDetail]:
    data = request.user.model_dump()
    return response_base.success(data=data)


@router.get('/{pk}/devices', summary='获取用户所有设备',
            # dependencies=[DependsJwtAuth]
            )
async def get_user_devices(
        db: CurrentSession, pk: Annotated[int, Path(description='用户 ID')]
) -> ResponseSchemaModel[list[GetDeviceDetail]]:
    data = await user_service.get_devices(db=db, pk=pk)
    return response_base.success(data=data)


@router.post('/bind', summary='设备绑定')
async def bind_device(
        db: CurrentSessionTransaction,
        obj: UserDeviceParam,
) -> ResponseModel:
    """设备绑定"""
    await user_service.bind_device(db=db, obj=obj)
    return response_base.success()


@router.post('/unbind', summary='设备解绑')
async def unbind_device(
        db: CurrentSessionTransaction,
        obj: UserDeviceParam,
) -> ResponseModel:
    """设备解绑"""
    await user_service.unbind_device(db=db, obj=obj)
    return response_base.success()
