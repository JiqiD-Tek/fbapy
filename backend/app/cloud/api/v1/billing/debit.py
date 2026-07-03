# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : debit.py
@Author  : guhua@jiqid.com
@Date    : 2026/07/01
"""

from fastapi import APIRouter

from backend.app.cloud.schema.billing import BillDebitUsageParam, BillDebitUsageResult
from backend.app.cloud.schema.user import DeviceAuthParam
from backend.app.cloud.service.billing_service import billing_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.auth import DependsDeviceAuth
from backend.database.db import CurrentSessionTransaction

router = APIRouter()


@router.post(
    '/debit',
    summary='按 usage 扣减 token',
)
async def debit_usage(
    db: CurrentSessionTransaction,
    obj: BillDebitUsageParam,
    auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> ResponseSchemaModel[BillDebitUsageResult]:
    data = await billing_service.debit_usage(db=db, obj=obj, auth_did=auth_ctx.did)
    return response_base.success(data=data)
