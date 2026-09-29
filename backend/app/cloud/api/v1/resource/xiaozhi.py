# -*- coding: UTF-8 -*-
"""小智设备服务接口。"""

from fastapi import APIRouter

from backend.app.cloud.schema.device.device_chat import CreateDeviceChatParam
from backend.app.cloud.schema.user import DeviceAuthParam
from backend.app.cloud.service.device_service import device_service
from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.auth import DependsDeviceAuth
from backend.database.db import CurrentSessionTransaction

router = APIRouter()


@router.post('/turn/chat', summary='保存小智设备聊天记录')
async def create_turn_chat(
        db: CurrentSessionTransaction,
        obj: CreateDeviceChatParam,
        auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> ResponseModel:
    await device_service.create_chat(db=db, did=auth_ctx.did, obj=obj)
    return response_base.success()
