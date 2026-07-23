# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : billing_service.py
@Author  : guhua@jiqid.com
@Date    : 2026/07/01
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from backend.app.cloud.crud.crud_billing import bill_account_dao, bill_txn_dao
from backend.app.cloud.schema.billing import BillTurnDebitParam, BillTurnDebitResult
from backend.common.exception import errors

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.app.cloud.model.billing import BillAccount, BillTxn

ACCOUNT_SUBJECT_DEVICE = 'DEVICE'
ACCOUNT_ACTIVE = 'ACTIVE'
ACCOUNT_BLOCKED = 'BLOCKED'
CHANGE_DEBIT = 'DEBIT'


class BillingService:
    """Billing service."""

    @classmethod
    async def debit_turn(
        cls,
        *,
        db: AsyncSession,
        obj: BillTurnDebitParam,
        auth_did: str,
    ) -> BillTurnDebitResult:
        account = await cls._get_or_create_device_account(db=db, did=auth_did)
        if account.status != ACCOUNT_ACTIVE:
            current = await cls._load_debit_result(
                db=db,
                session_id=obj.session_id,
                sentence_id=obj.sentence_id,
            )
            if current is not None:
                return current
            raise errors.ForbiddenError(msg='计费账户不可用')

        amount_token = obj.amount_token
        balance_token = account.balance_token - amount_token
        account_status = cls._account_status_from_balance(balance_token)
        txn_obj = {
            'account_id': account.id,
            'session_id': obj.session_id,
            'sentence_id': obj.sentence_id,
            'amount_token': amount_token,
            'balance_token': balance_token,
            'change_type': CHANGE_DEBIT,
        }

        try:
            async with db.begin_nested():
                txn = await bill_txn_dao.create(db, obj=txn_obj)
        except IntegrityError:
            current = await cls._load_debit_result(
                db=db,
                session_id=obj.session_id,
                sentence_id=obj.sentence_id,
            )
            if current is not None:
                return current
            raise

        account.balance_token = balance_token
        account.status = account_status
        return cls._build_debit_result(txn=txn)

    @classmethod
    async def _load_debit_result(
        cls,
        *,
        db: AsyncSession,
        session_id: str,
        sentence_id: str,
    ) -> BillTurnDebitResult | None:
        txn = await bill_txn_dao.get_by_session_sentence(
            db,
            session_id=session_id,
            sentence_id=sentence_id,
        )
        if txn is None:
            return None
        return cls._build_debit_result(txn=txn)

    @classmethod
    async def _get_or_create_device_account(cls, *, db: AsyncSession, did: str) -> BillAccount:
        account = await bill_account_dao.get_by_subject_for_update(
            db,
            subject_type=ACCOUNT_SUBJECT_DEVICE,
            subject_key=did,
        )
        if account is not None:
            return account

        try:
            async with db.begin_nested():
                account = await bill_account_dao.create(
                    db,
                    subject_type=ACCOUNT_SUBJECT_DEVICE,
                    subject_key=did,
                )
        except IntegrityError:
            account = await bill_account_dao.get_by_subject_for_update(
                db,
                subject_type=ACCOUNT_SUBJECT_DEVICE,
                subject_key=did,
            )
        if account is None:
            raise errors.ServerError(msg='创建计费账户失败')
        return account

    @staticmethod
    def _account_status_from_balance(balance_token: int) -> str:
        return ACCOUNT_BLOCKED if balance_token <= 0 else ACCOUNT_ACTIVE

    @classmethod
    def _build_debit_result(cls, *, txn: BillTxn) -> BillTurnDebitResult:
        account_status = cls._account_status_from_balance(txn.balance_token)
        return BillTurnDebitResult(
            account_id=txn.account_id,
            session_id=txn.session_id,
            sentence_id=txn.sentence_id,
            amount_token=txn.amount_token,
            balance_token=txn.balance_token,
            account_status=account_status,
        )


billing_service: BillingService = BillingService()
