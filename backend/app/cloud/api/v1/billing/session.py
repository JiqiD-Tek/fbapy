# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : session.py
@Author  : guhua@jiqid.com
@Date    : 2026/07/01
"""

from fastapi import APIRouter

from backend.app.cloud.schema.billing import (
    BillCloseSessionParam,
    BillCloseSessionResult,
    BillOpenSessionParam,
    BillOpenSessionResult,
)
from backend.app.cloud.schema.user import DeviceAuthParam
from backend.app.cloud.service.billing_service import billing_service
from backend.common.security.auth import DependsDeviceAuth
from backend.database.db import CurrentSessionTransaction

router = APIRouter()


@router.post(
    '/open',
    summary='打开计费会话',
)
async def open_session(
    db: CurrentSessionTransaction,
    obj: BillOpenSessionParam,
    auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> BillOpenSessionResult:
    return await billing_service.open_session(db=db, obj=obj, auth_did=auth_ctx.did)


@router.post(
    '/close',
    summary='关闭计费会话',
)
async def close_session(
    db: CurrentSessionTransaction,
    obj: BillCloseSessionParam,
    auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> BillCloseSessionResult:
    return await billing_service.close_session(db=db, obj=obj, auth_did=auth_ctx.did)
