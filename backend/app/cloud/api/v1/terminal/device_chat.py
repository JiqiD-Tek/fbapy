# -*- coding: UTF-8 -*-
"""
Device chat APIs.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from backend.app.cloud.schema.device_chat import CreateDeviceChatParam, GetDeviceChatDetail
from backend.app.cloud.schema.user import DeviceAuthParam
from backend.app.cloud.service.device_service import device_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.auth import DependsDeviceAuth
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.post('', summary='保存设备聊天记录', dependencies=[DependsDeviceAuth])
async def create_device_chat(
    db: CurrentSessionTransaction,
    obj: CreateDeviceChatParam,
    auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> ResponseSchemaModel[GetDeviceChatDetail]:
    chat = await device_service.create_chat(db=db, did=auth_ctx.did, obj=obj)
    return response_base.success(data=GetDeviceChatDetail.model_validate(chat))


@router.get('', summary='分页获取设备聊天记录', dependencies=[DependsJwtAuth, DependsPagination])
async def get_device_chat_paginated(
    db: CurrentSession,
    device_id: Annotated[int | None, Query(description='Device ID')] = None,
    toy_id: Annotated[int | None, Query(description='Toy ID')] = None,
    user_id: Annotated[int | None, Query(description='User ID')] = None,
    baby_id: Annotated[int | None, Query(description='Baby ID')] = None,
) -> ResponseSchemaModel[PageData[GetDeviceChatDetail]]:
    page_data = await device_service.get_chat_list(
        db=db,
        device_id=device_id,
        toy_id=toy_id,
        user_id=user_id,
        baby_id=baby_id,
    )
    return response_base.success(data=page_data)
