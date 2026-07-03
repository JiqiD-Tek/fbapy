# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : billing_service.py
@Author  : guhua@jiqid.com
@Date    : 2026/07/01
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.crud_billing import (
    bill_account_dao,
    bill_session_dao,
    bill_txn_dao,
)
from backend.app.cloud.model.billing import BillAccount, BillSession, BillTxn
from backend.app.cloud.schema.billing import (
    BillDebitUsageParam,
    BillDebitUsageResult,
    BillCloseSessionParam,
    BillCloseSessionResult,
    BillOpenSessionParam,
    BillOpenSessionResult,
)
from backend.common.exception import errors

ACCOUNT_ACTIVE = 'ACTIVE'
ACCOUNT_BLOCKED = 'BLOCKED'
SESSION_OPEN = 'OPEN'
SESSION_BLOCKED = 'BLOCKED'
SESSION_CLOSED = 'CLOSED'
SESSION_ABORTED = 'ABORTED'
CHANGE_DEBIT = 'DEBIT'
SESSION_ACTIVITY_UPDATE_INTERVAL_SECONDS = 5.0


class BillingService:
    """计费服务。"""

    @staticmethod
    async def open_session(*, db: AsyncSession, obj: BillOpenSessionParam, auth_did: str) -> BillOpenSessionResult:
        BillingService._ensure_auth_did(device_did=obj.device_did, auth_did=auth_did)
        current = await bill_session_dao.get_by_session_id(db, session_id=obj.session_id)
        if current is not None:
            account = await bill_account_dao.get_for_update(db, account_id=current.account_id)
            if account is None:
                raise errors.NotFoundError(msg='计费账户不存在')
            BillingService._ensure_session_owner(session=current, device_did=obj.device_did)
            return BillingService._build_open_result(account=account, session=current)

        BillingService._validate_open_subject(obj)
        account = await bill_account_dao.get_by_subject_for_update(
            db,
            subject_type=obj.subject_type,
            subject_key=obj.subject_key,
        )
        if account is None:
            try:
                account = await bill_account_dao.create(
                    db,
                    subject_type=obj.subject_type,
                    subject_key=obj.subject_key,
                )
            except IntegrityError:
                account = await bill_account_dao.get_by_subject_for_update(
                    db,
                    subject_type=obj.subject_type,
                    subject_key=obj.subject_key,
                )
        if account is None:
            raise errors.ServerError(msg='创建计费账户失败')
        if account.status != ACCOUNT_ACTIVE:
            raise errors.ForbiddenError(msg='计费账户不可用')

        try:
            session = await bill_session_dao.create(
                db,
                session_id=obj.session_id,
                account_id=account.id,
                device_did=obj.device_did,
                status=SESSION_OPEN,
                started_at=obj.started_at,
                last_activity_at=obj.started_at,
            )
        except IntegrityError:
            session = await bill_session_dao.get_by_session_id(db, session_id=obj.session_id)
        if session is None:
            raise errors.ServerError(msg='创建计费会话失败')
        return BillingService._build_open_result(account=account, session=session)

    @classmethod
    async def debit_usage(cls, *, db: AsyncSession, obj: BillDebitUsageParam, auth_did: str) -> BillDebitUsageResult:
        current = await cls._load_debit_result(db=db, usage_id=obj.usage_id)
        if current is not None:
            return current

        session_bundle = await bill_session_dao.get_with_account_for_update(db, session_id=obj.session_id)
        if session_bundle is None:
            raise errors.NotFoundError(msg='计费会话不存在')

        session, account = session_bundle
        cls._ensure_auth_did(device_did=session.device_did, auth_did=auth_did)
        if session.status not in {SESSION_OPEN, SESSION_BLOCKED}:
            raise errors.ConflictError(msg='计费会话已关闭')

        amount_token = cls._require_non_negative(obj.usage_token, 'usage_token')
        balance_after_token = account.balance_token - amount_token
        should_block = amount_token > 0 and balance_after_token <= 0
        next_account_status = ACCOUNT_BLOCKED if should_block else account.status
        next_session_status = SESSION_BLOCKED if should_block else session.status

        txn_obj = {
            'charge_id': obj.usage_id,
            'account_id': account.id,
            'change_type': CHANGE_DEBIT,
            'delta_token': -amount_token,
            'balance_after_token': balance_after_token,
            'account_status_after': next_account_status,
            'session_status_after': next_session_status,
            'usage_id': obj.usage_id,
            'session_id': obj.session_id,
            'turn_no': obj.turn_no,
            'stage_no': obj.stage_no,
            'usage_kind': obj.usage_kind,
            'usage_token': amount_token,
            'provider': obj.provider,
            'occurred_at': obj.occurred_at,
        }

        try:
            async with db.begin_nested():
                txn = await bill_txn_dao.create(db, obj=txn_obj)
        except IntegrityError:
            current = await cls._load_debit_result(db=db, usage_id=obj.usage_id)
            if current is not None:
                return current
            raise

        account.balance_token = balance_after_token
        account.status = next_account_status

        if should_block:
            session.status = SESSION_BLOCKED
            session.last_activity_at = obj.occurred_at
        elif session.status == SESSION_OPEN and cls._should_touch_session_activity(session=session, occurred_at=obj.occurred_at):
            session.last_activity_at = obj.occurred_at

        return cls._build_debit_result(txn=txn)

    @staticmethod
    async def close_session(*, db: AsyncSession, obj: BillCloseSessionParam, auth_did: str) -> BillCloseSessionResult:
        session = await bill_session_dao.get_by_session_id_for_update(db, session_id=obj.session_id)
        if session is None:
            raise errors.NotFoundError(msg='计费会话不存在')
        BillingService._ensure_auth_did(device_did=session.device_did, auth_did=auth_did)

        if session.status in {SESSION_CLOSED, SESSION_ABORTED}:
            return BillCloseSessionResult(
                session_id=session.session_id,
                session_status=session.status,
            )

        session.status = obj.status
        session.ended_at = obj.ended_at
        session.last_activity_at = obj.ended_at
        return BillCloseSessionResult(
            session_id=session.session_id,
            session_status=session.status,
        )

    @staticmethod
    async def _load_debit_result(*, db: AsyncSession, usage_id: str) -> BillDebitUsageResult | None:
        txn = await bill_txn_dao.get_by_usage_id(db, usage_id=usage_id)
        if txn is None:
            return None
        return BillingService._build_debit_result(txn=txn)

    @staticmethod
    def _build_open_result(*, account: BillAccount, session: BillSession) -> BillOpenSessionResult:
        return BillOpenSessionResult(
            account_id=account.id,
            balance_token=account.balance_token,
            account_status=account.status,
            session_status=session.status,
        )

    @staticmethod
    def _validate_open_subject(obj: BillOpenSessionParam) -> None:
        if obj.subject_type == 'DEVICE' and obj.subject_key != obj.device_did:
            raise errors.RequestError(msg='DEVICE 计费主体必须使用 device_did 作为 subject_key')

    @staticmethod
    def _ensure_session_owner(*, session: BillSession, device_did: str) -> None:
        if session.device_did != device_did:
            raise errors.ConflictError(msg='session_id 已绑定其他设备')

    @staticmethod
    def _ensure_auth_did(*, device_did: str, auth_did: str) -> None:
        if device_did != auth_did:
            raise errors.ForbiddenError(msg='device_did 与当前设备认证不一致')

    @staticmethod
    def _build_debit_result(*, txn: BillTxn) -> BillDebitUsageResult:
        return BillDebitUsageResult(
            account_id=txn.account_id,
            usage_id=txn.usage_id or txn.charge_id,
            charge_id=txn.charge_id,
            amount_token=txn.usage_token or max(-txn.delta_token, 0),
            balance_after_token=txn.balance_after_token,
            account_status=txn.account_status_after,
            session_status=txn.session_status_after,
            should_stop=txn.session_status_after == SESSION_BLOCKED,
        )

    @staticmethod
    def _should_touch_session_activity(*, session: BillSession, occurred_at) -> bool:
        if session.last_activity_at is None:
            return True
        if occurred_at <= session.last_activity_at:
            return False
        return (occurred_at - session.last_activity_at).total_seconds() >= SESSION_ACTIVITY_UPDATE_INTERVAL_SECONDS

    @staticmethod
    def _require_non_negative(value: int, field_name: str) -> int:
        if value < 0:
            raise errors.RequestError(msg=f'{field_name} 不能小于 0')
        return value


billing_service: BillingService = BillingService()
