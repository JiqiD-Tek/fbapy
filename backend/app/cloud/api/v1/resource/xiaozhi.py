# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : xiaozhi.py
@Author  : guhua@jiqid.com
@Date    : 2026/07/22 13:47
"""

from fastapi import APIRouter

from backend.app.cloud.schema.billing import BillTurnDebitParam, BillTurnDebitResult
from backend.app.cloud.schema.device_chat import CreateDeviceChatParam
from backend.app.cloud.schema.user import DeviceAuthParam
from backend.app.cloud.service.billing_service import billing_service
from backend.app.cloud.service.device_service import device_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base, ResponseModel
from backend.common.security.auth import DependsDeviceAuth
from backend.database.db import CurrentSessionTransaction

router = APIRouter()


@router.post(
    '/billing/debit',
    summary='扣减小智一轮对话费用',
)
async def debit_billing_turn(
        db: CurrentSessionTransaction,
        obj: BillTurnDebitParam,
        auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> ResponseSchemaModel[BillTurnDebitResult]:
    data = await billing_service.debit_turn(db=db, obj=obj, auth_did=auth_ctx.did)
    return response_base.success(data=data)


@router.post(
    '/turn/chat',
    summary='保存小智设备聊天记录',
)
async def create_turn_chat(
        db: CurrentSessionTransaction,
        obj: CreateDeviceChatParam,
        auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> ResponseModel:
    await device_service.create_chat(db=db, did=auth_ctx.did, obj=obj)
    return response_base.success()
