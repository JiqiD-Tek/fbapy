from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model.billing import BillAccount, BillTxn


class CRUDBillAccount(CRUDPlus[BillAccount]):
    async def get_by_subject_for_update(
        self,
        db: AsyncSession,
        *,
        subject_type: str,
        subject_key: str,
    ) -> BillAccount | None:
        stmt = (
            select(BillAccount)
            .where(BillAccount.subject_type == subject_type, BillAccount.subject_key == subject_key)
            .with_for_update()
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_update(self, db: AsyncSession, *, account_id: int) -> BillAccount | None:
        stmt = select(BillAccount).where(BillAccount.id == account_id).with_for_update().limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        *,
        subject_type: str,
        subject_key: str,
        balance_credits: int,
        weekly_credits_quota: int | None,
        status: str,
        weekly_credits_usage: int = 0,
        weekly_reset_at: datetime | None = None,
    ) -> BillAccount:
        account = self.model(
            subject_type=subject_type,
            subject_key=subject_key,
            balance_credits=balance_credits,
            weekly_credits_quota=weekly_credits_quota,
            weekly_credits_usage=weekly_credits_usage,
            weekly_reset_at=weekly_reset_at,
            status=status,
        )
        db.add(account)
        await db.flush()
        return account


class CRUDBillTxn(CRUDPlus[BillTxn]):
    async def get_by_business(
        self,
        db: AsyncSession,
        *,
        biz_type: str,
        biz_id: str,
        usage_type: str,
    ) -> BillTxn | None:
        stmt = (
            select(BillTxn)
            .where(
                BillTxn.biz_type == biz_type,
                BillTxn.biz_id == biz_id,
                BillTxn.usage_type == usage_type,
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, *, obj: dict[str, Any] | BillTxn) -> BillTxn:
        txn = self.model(**obj) if isinstance(obj, dict) else obj
        db.add(txn)
        await db.flush()
        return txn


bill_account_dao: CRUDBillAccount = CRUDBillAccount(BillAccount)
bill_txn_dao: CRUDBillTxn = CRUDBillTxn(BillTxn)
