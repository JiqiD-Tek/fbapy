from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model.billing import BillAccount, BillSession, BillTxn


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
        return await self.create_model(
            db,
            {
                'subject_type': subject_type,
                'subject_key': subject_key,
                'balance_token': balance_token,
                'status': status,
            },
            flush=True,
        )


class CRUDBillSession(CRUDPlus[BillSession]):
    async def get_by_session_id(self, db: AsyncSession, *, session_id: str) -> BillSession | None:
        return await self.select_model_by_column(db, session_id=session_id)

    async def get_by_session_id_for_update(self, db: AsyncSession, *, session_id: str) -> BillSession | None:
        stmt = select(BillSession).where(BillSession.session_id == session_id).with_for_update().limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_account_for_update(
        self,
        db: AsyncSession,
        *,
        session_id: str,
    ) -> tuple[BillSession, BillAccount] | None:
        stmt = (
            select(BillSession, BillAccount)
            .join(BillAccount, BillAccount.id == BillSession.account_id)
            .where(BillSession.session_id == session_id)
            .with_for_update()
            .limit(1)
        )
        result = await db.execute(stmt)
        row = result.first()
        if row is None:
            return None
        return row[0], row[1]

    async def create(
        self,
        db: AsyncSession,
        *,
        session_id: str,
        account_id: int,
        device_did: str,
        status: str,
        started_at,
        last_activity_at,
    ) -> BillSession:
        return await self.create_model(
            db,
            {
                'session_id': session_id,
                'account_id': account_id,
                'device_did': device_did,
                'status': status,
                'started_at': started_at,
                'last_activity_at': last_activity_at,
            },
            flush=True,
        )


class CRUDBillTxn(CRUDPlus[BillTxn]):
    async def get_by_usage_id(self, db: AsyncSession, *, usage_id: str) -> BillTxn | None:
        return await self.select_model_by_column(db, usage_id=usage_id)

    async def create(self, db: AsyncSession, *, obj: dict) -> BillTxn:
        return await self.create_model(db, obj, flush=True)


bill_account_dao: CRUDBillAccount = CRUDBillAccount(BillAccount)
bill_session_dao: CRUDBillSession = CRUDBillSession(BillSession)
bill_txn_dao: CRUDBillTxn = CRUDBillTxn(BillTxn)
