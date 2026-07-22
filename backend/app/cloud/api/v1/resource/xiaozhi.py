# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : xiaozhi.py
@Author  : guhua@jiqid.com
@Date    : 2026/07/22 13:47
"""

from fastapi import APIRouter

from backend.app.cloud.schema.billing import (
    BillCloseSessionParam,
    BillCloseSessionResult,
    BillDebitUsageParam,
    BillDebitUsageResult,
    BillOpenSessionParam,
    BillOpenSessionResult,
)
from backend.app.cloud.schema.device_chat import CreateDeviceChatParam, GetDeviceChatDetail
from backend.app.cloud.schema.user import DeviceAuthParam
from backend.app.cloud.service.billing_service import billing_service
from backend.app.cloud.service.device_service import device_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.auth import DependsDeviceAuth
from backend.database.db import CurrentSessionTransaction

router = APIRouter()


@router.post(
    '/billing/session/open',
    summary='打开小智计费会话',
)
async def open_billing_session(
        db: CurrentSessionTransaction,
        obj: BillOpenSessionParam,
        auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> BillOpenSessionResult:
    return await billing_service.open_session(db=db, obj=obj, auth_did=auth_ctx.did)


@router.post(
    '/billing/session/close',
    summary='关闭小智计费会话',
)
async def close_billing_session(
        db: CurrentSessionTransaction,
        obj: BillCloseSessionParam,
        auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> BillCloseSessionResult:
    return await billing_service.close_session(db=db, obj=obj, auth_did=auth_ctx.did)


@router.post(
    '/billing/usage/debit',
    summary='按 turn 扣减 token',
)
async def debit_billing_usage(
        db: CurrentSessionTransaction,
        obj: BillDebitUsageParam,
        auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> BillDebitUsageResult:
    return await billing_service.debit_usage(db=db, obj=obj, auth_did=auth_ctx.did)


@router.post(
    '/device-chat',
    summary='保存小智设备聊天记录',
)
async def save_xiaozhi_device_chat_record(
        db: CurrentSessionTransaction,
        obj: CreateDeviceChatParam,
        auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> ResponseSchemaModel[GetDeviceChatDetail]:
    chat = await device_service.create_chat(db=db, did=auth_ctx.did, obj=obj)
    return response_base.success(data=GetDeviceChatDetail.model_validate(chat))
