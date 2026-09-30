# -*- coding: UTF-8 -*-
"""终端计费接口。"""

from fastapi import APIRouter

from backend.app.cloud.schema.billing import (
    BillingAccountQueryParam,
    BillingAccountQuotaResult,
    BillingSessionResult,
    BillTurnDebitParam,
    BillTurnDebitResult,
)
from backend.app.cloud.schema.user import DeviceAuthParam
from backend.app.cloud.service.billing_service import BILL_BIZ_CHAT, billing_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.auth import DependsDeviceAuth
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSessionTransaction

router = APIRouter()


@router.post(
    '/account',
    summary='查询设备计费额度',
    dependencies=[DependsJwtAuth],
)
async def get_billing_account(
        db: CurrentSessionTransaction,
        obj: BillingAccountQueryParam,
) -> ResponseSchemaModel[BillingAccountQuotaResult]:
    data = await billing_service.get_device_account_quota(db=db, device_did=obj.device_did)
    return response_base.success(data=data)


@router.post('/session', summary='创建计费会话并获取额度')
async def open_billing_session(
        db: CurrentSessionTransaction,
        auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> ResponseSchemaModel[BillingSessionResult]:
    data = await billing_service.open_session(db=db, auth_did=auth_ctx.did)
    return response_base.success(data=data)


@router.post('/debit', summary='扣减一次业务额度')
async def debit_billing(
        db: CurrentSessionTransaction,
        obj: BillTurnDebitParam,
        auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> ResponseSchemaModel[BillTurnDebitResult]:
    data = await billing_service.debit(
        db=db,
        auth_did=auth_ctx.did,
        biz_type=BILL_BIZ_CHAT,
        biz_id=f'{obj.session_id}:{obj.sentence_id}',
        quantity=obj.quantity,
        usage_type=obj.usage_type,
        session_id=obj.session_id,
        sentence_id=obj.sentence_id,
    )
    return response_base.success(data=data)
