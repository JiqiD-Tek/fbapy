from __future__ import annotations

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
        balance_token: int = 0,
        status: str = 'ACTIVE',
    ) -> BillAccount:
        account = self.model(
            subject_type=subject_type,
            subject_key=subject_key,
            balance_token=balance_token,
            status=status,
        )
        db.add(account)
        await db.flush()
        return account


class CRUDBillTxn(CRUDPlus[BillTxn]):
    async def get_by_session_sentence(
        self,
        db: AsyncSession,
        *,
        session_id: str,
        sentence_id: str,
    ) -> BillTxn | None:
        stmt = (
            select(BillTxn)
            .where(BillTxn.session_id == session_id, BillTxn.sentence_id == sentence_id)
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
