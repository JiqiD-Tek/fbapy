# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : billing.py
@Author  : guhua@jiqid.com
@Date    : 2026/07/01
"""

from typing import Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

BillSubjectType = Literal['DEVICE']
BillAccountStatus = Literal['ACTIVE', 'BLOCKED']


class BillingSchemaBase(SchemaBase):
    """Billing schema base that rejects removed legacy fields."""

    model_config = ConfigDict(extra='forbid')


class BillTurnDebitParam(BillingSchemaBase):
    """Turn-level debit request for xiaozhi."""

    session_id: str = Field(min_length=1, max_length=64, description='Connection-level session_id')
    sentence_id: str = Field(min_length=1, max_length=64, description='Turn-level sentence_id')
    amount_token: int = Field(ge=0, description='Billing amount for the current turn')


class BillTurnDebitResult(BillingSchemaBase):
    """Turn-level debit response for xiaozhi."""

    account_id: int = Field(description='Billing account ID')
    session_id: str = Field(description='Connection-level session_id')
    sentence_id: str = Field(description='Turn-level sentence_id')
    amount_token: int = Field(ge=0, description='Billing amount for the current turn')
    balance_token: int = Field(description='Balance snapshot after this debit, in token')
    account_status: BillAccountStatus = Field(description='Derived account status after this debit')
