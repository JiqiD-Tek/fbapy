# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : billing.py
@Author  : guhua@jiqid.com
@Date    : 2026/07/01
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from backend.common.schema import SchemaBase

BillSubjectType = Literal['DEVICE']
BillAccountStatus = Literal['ACTIVE', 'BLOCKED']


class CreditUsageType(str, Enum):
    """计费原始用量类型。"""

    LLM_INPUT_CHARACTERS = 'llm_input_characters'
    LLM_OUTPUT_CHARACTERS = 'llm_output_characters'
    TTS_CHARACTERS = 'tts_characters'
    ASR_SECONDS = 'asr_seconds'


class BillingSchemaBase(SchemaBase):
    """计费数据模型基类，禁止传入已移除的旧字段。"""

    model_config = ConfigDict(extra='forbid')


class BillTurnDebitParam(BillingSchemaBase):
    """小智单轮对话扣费参数。"""

    session_id: str = Field(min_length=1, max_length=64, description='连接级 session_id')
    sentence_id: str = Field(min_length=1, max_length=64, description='对话轮次级 sentence_id')
    quantity: int | float = Field(gt=0, description='本次原始用量，单位由 usage_type 指定')
    usage_type: CreditUsageType = Field(description='原始用量类型')


class BillingSessionResult(BillingSchemaBase):
    """终端计费会话和额度快照。"""

    session_id: str = Field(description='计费会话 ID')
    account_id: int = Field(description='计费账户 ID')
    account_status: BillAccountStatus = Field(description='计费账户状态')
    balance_credits: int = Field(description='充值积分余额')
    weekly_credits_quota: int | None = Field(description='本周赠送积分额度，NULL 表示不限制')
    weekly_credits_usage: int = Field(ge=0, description='本周已使用的赠送积分')
    weekly_credits_remaining: int | None = Field(description='本周赠送积分剩余量')
    available_credits: int | None = Field(description='当前可用总积分，NULL 表示不限制')
    weekly_reset_at: datetime = Field(description='本周额度下次重置时间')


class BillingAccountQueryParam(BillingSchemaBase):
    """查询设备计费账户参数。"""

    device_did: str = Field(min_length=1, max_length=64, description='设备 DID')

    @field_validator('device_did')
    @classmethod
    def normalize_device_did(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('设备 DID 不能为空')
        return normalized


class BillingAccountQuotaResult(BillingSchemaBase):
    """设备计费账户额度信息。"""

    device_did: str = Field(description='设备 DID')
    account_id: int = Field(description='计费账户 ID')
    account_status: BillAccountStatus = Field(description='计费账户状态')
    balance_credits: int = Field(description='充值积分余额')
    weekly_credits_quota: int | None = Field(description='本周赠送积分额度，NULL 表示不限制')
    weekly_credits_usage: int = Field(description='本周已使用的赠送积分')
    weekly_credits_remaining: int | None = Field(description='本周赠送积分剩余量')
    available_credits: int | None = Field(description='当前可用总积分，NULL 表示不限制')
    weekly_reset_at: datetime = Field(description='本周额度下次重置时间')


class BillTurnDebitResult(BillingSchemaBase):
    """小智单轮对话扣费结果。"""

    account_id: int = Field(description='计费账户 ID')
    session_id: str = Field(description='连接级 session_id')
    sentence_id: str = Field(description='对话轮次级 sentence_id')
    amount_credits: int = Field(gt=0, description='当前轮次扣费积分')
    balance_credits: int = Field(description='本次扣费后的充值积分余额快照')
    account_status: BillAccountStatus = Field(description='本次扣费后的账户状态')
    weekly_credits_quota: int | None = Field(description='周赠送积分额度，NULL 表示不限制')
    weekly_credits_usage: int = Field(ge=0, description='当前周已使用的赠送积分数量')
    weekly_credits_remaining: int | None = Field(description='当前周剩余的赠送积分数量，NULL 表示不限制')
    weekly_reset_at: datetime = Field(description='周额度下次恢复时间')
