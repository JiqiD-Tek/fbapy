# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : billing_service.py
@Author  : guhua@jiqid.com
@Date    : 2026/07/01
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from backend.app.cloud.crud.crud_billing import bill_account_dao, bill_txn_dao
from backend.app.cloud.schema.billing import (
    BillingAccountQuotaResult,
    BillingSessionResult,
    BillTurnDebitResult,
)
from backend.common.exception import errors
from backend.common.response.response_code import CustomErrorCode
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.app.cloud.model.billing import BillAccount, BillTxn

ACCOUNT_SUBJECT_DEVICE = 'DEVICE'
ACCOUNT_ACTIVE = 'ACTIVE'
CHANGE_DEBIT = 'DEBIT'
BILL_BIZ_CHAT = 'CHAT'
BILL_BIZ_STORY = 'STORY'


class BillingService:
    """计费服务。"""

    @classmethod
    async def open_session(cls, *, db: AsyncSession, auth_did: str) -> BillingSessionResult:
        """创建终端计费会话，并返回当前额度快照。"""
        account = await cls.get_or_create_device_account(db=db, did=auth_did)
        now = timezone.now()
        weekly_reset_at = cls._get_weekly_reset_at(now)
        cls._reset_weekly_usage(account=account, now=now, next_reset_at=weekly_reset_at)
        weekly_remaining = cls._weekly_token_remaining(account)
        available_token = None if weekly_remaining is None else weekly_remaining + account.balance_token
        return BillingSessionResult(
            session_id=uuid4().hex,
            account_id=account.id,
            account_status=account.status,
            balance_token=account.balance_token,
            weekly_token_quota=account.weekly_token_quota,
            weekly_token_usage=account.weekly_token_usage,
            weekly_token_remaining=weekly_remaining,
            available_token=available_token,
            weekly_reset_at=weekly_reset_at,
        )

    @classmethod
    async def get_device_account_quota(
            cls,
            *,
            db: AsyncSession,
            device_did: str,
    ) -> BillingAccountQuotaResult:
        """查询设备额度，账户不存在时初始化默认账户。"""
        account = await cls.get_or_create_device_account(db=db, did=device_did)

        now = timezone.now()
        next_reset_at = cls._get_weekly_reset_at(now)
        reset_at = account.weekly_reset_at
        usage = account.weekly_token_usage
        if reset_at is None or now >= reset_at:
            reset_at = next_reset_at
            usage = 0
        weekly_remaining = cls._weekly_token_remaining_for_values(
            quota=account.weekly_token_quota,
            usage=usage,
        )
        available_token = None if weekly_remaining is None else weekly_remaining + account.balance_token
        return BillingAccountQuotaResult(
            device_did=device_did,
            account_id=account.id,
            account_status=account.status,
            balance_token=account.balance_token,
            weekly_token_quota=account.weekly_token_quota,
            weekly_token_usage=usage,
            weekly_token_remaining=weekly_remaining,
            available_token=available_token,
            weekly_reset_at=reset_at,
        )

    @classmethod
    async def debit(
        cls,
        *,
        db: AsyncSession,
        auth_did: str,
        biz_type: str,
        biz_id: str,
        amount_token: int,
        session_id: str | None = None,
        sentence_id: str | None = None,
    ) -> BillTurnDebitResult:
        """按业务幂等标识扣费，聊天和故事任务共用同一套额度逻辑。"""
        if amount_token <= 0:
            raise errors.RequestError(msg='扣费金额必须大于 0')
        session_id = session_id or f'{biz_type.lower()}:{biz_id}'
        sentence_id = sentence_id or 'submit'
        account = await cls.get_or_create_device_account(db=db, did=auth_did)
        now = timezone.now()
        weekly_reset_at = cls._get_weekly_reset_at(now)
        cls._reset_weekly_usage(account=account, now=now, next_reset_at=weekly_reset_at)

        current = await cls._load_debit_result(
            db=db,
            account=account,
            biz_type=biz_type,
            biz_id=biz_id,
            weekly_reset_at=weekly_reset_at,
        )
        if current is not None:
            return current

        if account.status != ACCOUNT_ACTIVE:
            raise errors.ForbiddenError(msg='计费账户不可用')

        weekly_token_amount = cls._weekly_token_amount(account=account, amount_token=amount_token)
        balance_token_amount = amount_token - weekly_token_amount
        if account.balance_token < balance_token_amount:
            raise errors.CustomError(
                error=CustomErrorCode.DEVICE_QUOTA_NOT_ENOUGH,
                msg='可用额度不足',
                data={
                    'balance_token': account.balance_token,
                    'weekly_token_quota': account.weekly_token_quota,
                    'weekly_token_usage': account.weekly_token_usage,
                    'weekly_token_remaining': cls._weekly_token_remaining(account),
                    'weekly_reset_at': weekly_reset_at.isoformat(),
                },
            )

        balance_token = account.balance_token - balance_token_amount
        txn_obj = {
            'account_id': account.id,
            'biz_type': biz_type,
            'biz_id': biz_id,
            'session_id': session_id,
            'sentence_id': sentence_id,
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
                account=account,
                biz_type=biz_type,
                biz_id=biz_id,
                weekly_reset_at=weekly_reset_at,
            )
            if current is not None:
                return current
            raise

        account.balance_token = balance_token
        account.weekly_token_usage += weekly_token_amount
        return cls._build_debit_result(
            txn=txn,
            account=account,
            weekly_reset_at=weekly_reset_at,
        )

    @classmethod
    async def _load_debit_result(
        cls,
        *,
        db: AsyncSession,
        account: BillAccount,
        biz_type: str,
        biz_id: str,
        weekly_reset_at: datetime,
    ) -> BillTurnDebitResult | None:
        txn = await bill_txn_dao.get_by_business(db, biz_type=biz_type, biz_id=biz_id)
        if txn is None:
            return None
        if txn.account_id != account.id:
            raise errors.ConflictError(msg='扣费幂等标识已被其他账户使用')
        return cls._build_debit_result(
            txn=txn,
            account=account,
            weekly_reset_at=weekly_reset_at,
        )

    @classmethod
    async def get_or_create_device_account(cls, *, db: AsyncSession, did: str) -> BillAccount:
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
                    balance_token=100_000_000,
                    weekly_reset_at=cls._get_weekly_reset_at(),
                    status=ACCOUNT_ACTIVE,
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
    def _get_weekly_reset_at(now: datetime | None = None) -> datetime:
        now = now or timezone.now()
        local_now = timezone.from_datetime(now)
        weekly_period_start = local_now.date() - timedelta(days=local_now.weekday())
        next_period_start = weekly_period_start + timedelta(days=7)
        return datetime.combine(next_period_start, time.min, tzinfo=timezone.tz_info)

    @staticmethod
    def _reset_weekly_usage(*, account: BillAccount, now: datetime, next_reset_at: datetime) -> None:
        if account.weekly_reset_at is not None and now < account.weekly_reset_at:
            return
        account.weekly_reset_at = next_reset_at
        account.weekly_token_usage = 0

    @staticmethod
    def _weekly_token_remaining(account: BillAccount) -> int | None:
        return BillingService._weekly_token_remaining_for_values(
            quota=account.weekly_token_quota,
            usage=account.weekly_token_usage,
        )

    @staticmethod
    def _weekly_token_remaining_for_values(*, quota: int | None, usage: int) -> int | None:
        if quota is None:
            return None
        return max(quota - usage, 0)

    @classmethod
    def _weekly_token_amount(cls, *, account: BillAccount, amount_token: int) -> int:
        weekly_token_remaining = cls._weekly_token_remaining(account)
        if weekly_token_remaining is None:
            return amount_token
        return min(amount_token, weekly_token_remaining)

    @classmethod
    def _build_debit_result(
        cls,
        *,
        txn: BillTxn,
        account: BillAccount,
        weekly_reset_at: datetime,
    ) -> BillTurnDebitResult:
        return BillTurnDebitResult(
            account_id=txn.account_id,
            session_id=txn.session_id,
            sentence_id=txn.sentence_id,
            amount_token=txn.amount_token,
            balance_token=txn.balance_token,
            account_status=account.status,
            weekly_token_quota=account.weekly_token_quota,
            weekly_token_usage=account.weekly_token_usage,
            weekly_token_remaining=cls._weekly_token_remaining(account),
            weekly_reset_at=weekly_reset_at,
        )


billing_service: BillingService = BillingService()
