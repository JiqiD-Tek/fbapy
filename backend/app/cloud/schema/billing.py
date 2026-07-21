# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : billing.py
@Author  : guhua@jiqid.com
@Date    : 2026/07/01
"""

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

BillSubjectType = Literal['DEVICE']
BillAccountStatus = Literal['ACTIVE', 'BLOCKED']
BillSessionStatus = Literal['OPEN', 'BLOCKED', 'CLOSED', 'ABORTED']
BillCloseSessionStatus = Literal['BLOCKED', 'CLOSED', 'ABORTED']


class BillingSchemaBase(SchemaBase):
    """Billing schema base that rejects removed legacy fields."""

    model_config = ConfigDict(extra='forbid')


class BillOpenSessionParam(BillingSchemaBase):
    """打开计费会话请求。"""

    session_id: str = Field(description='会话 ID')
    subject_type: BillSubjectType = Field(description='计费主体类型')
    subject_key: str = Field(description='计费主体标识')
    device_did: str = Field(description='设备 DID')
    started_at: datetime = Field(description='会话开始时间')


class BillOpenSessionResult(BillingSchemaBase):
    """打开计费会话响应。"""

    ok: bool = Field(True, description='是否成功')
    account_id: int = Field(description='计费主体 ID')
    balance_token: int = Field(description='当前余额，单位 token')
    account_status: BillAccountStatus = Field(description='账户状态')
    session_status: BillSessionStatus = Field(description='会话状态')


class BillDebitUsageParam(BillingSchemaBase):
    """turn 扣费请求。"""

    usage_id: str = Field(description='全局唯一的 turn 幂等 ID')
    session_id: str = Field(description='会话 ID')
    turn_no: int = Field(ge=0, description='回合号')
    usage_token: int = Field(ge=0, description='本次 turn 汇总 token')


class BillDebitUsageResult(BillingSchemaBase):
    """turn 扣费响应。"""

    ok: bool = Field(True, description='是否成功')
    account_id: int = Field(description='计费主体 ID')
    usage_id: str = Field(description='turn 幂等 ID')
    amount_token: int = Field(description='本次扣减 token')
    balance_after_token: int = Field(description='扣费后余额，单位 token')
    account_status: BillAccountStatus = Field(description='账户状态')
    session_status: BillSessionStatus = Field(description='会话状态')
    should_stop: bool = Field(False, description='是否应停止当前会话')


class BillCloseSessionParam(BillingSchemaBase):
    """关闭计费会话请求。"""

    session_id: str = Field(description='会话 ID')
    status: BillCloseSessionStatus = Field(description='关闭后的会话状态')
    ended_at: datetime = Field(description='会话结束时间')


class BillCloseSessionResult(BillingSchemaBase):
    """关闭计费会话响应。"""

    ok: bool = Field(True, description='是否成功')
    session_id: str = Field(description='会话 ID')
    session_status: BillSessionStatus = Field(description='会话状态')
