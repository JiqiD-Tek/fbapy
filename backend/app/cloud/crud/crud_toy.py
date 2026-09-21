# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : crud_toy.py
@Author  : OpenAI
@Date    : 2026/07/06
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import Toy, ToyNfc, ToySeries
from backend.app.cloud.schema.device.toy import (
    CreateToyParam,
    CreateToySeriesParam,
    CreateToyNfcParam,
    UpdateToyParam,
    UpdateToyNfcParam,
    UpdateToySeriesParam,
)


class CRUDToySeries(CRUDPlus[ToySeries]):
    async def get(self, db: AsyncSession, pk: int) -> ToySeries | None:
        stmt = sa.select(self.model).where(self.model.deleted == 0, self.model.id == pk).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_select(
        self,
        *,
        name: str | None,
        status: int | None,
    ) -> Select:
        stmt = sa.select(self.model).where(self.model.deleted == 0)

        if name is not None:
            stmt = stmt.where(self.model.name.like(f'%{name}%'))
        if status is not None:
            stmt = stmt.where(self.model.status == status)

        return stmt.order_by(self.model.sort.asc(), self.model.id.desc())

    async def create(self, db: AsyncSession, obj: CreateToySeriesParam) -> ToySeries:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateToySeriesParam | dict[str, Any]) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id=pk)


class CRUDToy(CRUDPlus[Toy]):
    async def get(self, db: AsyncSession, pk: int) -> Toy | None:
        return await self.select_model(db, pk)

    async def get_by_ids(
        self,
        db: AsyncSession,
        *,
        ids: Sequence[int],
        enabled_only: bool = False,
    ) -> Sequence[Toy]:
        if not ids:
            return []

        stmt = sa.select(self.model).where(self.model.deleted == 0, self.model.id.in_(ids))
        if enabled_only:
            stmt = stmt.where(self.model.status == 1)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_by_nfc_code(
        self,
        db: AsyncSession,
        *,
        nfc_code: str,
        enabled_only: bool = False,
    ) -> Toy | None:
        stmt = (
            sa.select(self.model)
            .join(ToyNfc, ToyNfc.toy_id == self.model.id)
            .where(
                self.model.deleted == 0,
                ToyNfc.deleted == 0,
                ToyNfc.status == 1,
                ToyNfc.nfc_code == nfc_code,
            )
        )
        if enabled_only:
            stmt = stmt.where(self.model.status == 1)
        result = await db.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def get_select(
        self,
        *,
        series_id: int | None,
        name: str | None,
        nfc_code: str | None,
        voice_language: str | None,
        status: int | None,
    ) -> Select:
        stmt = sa.select(self.model).where(self.model.deleted == 0)

        if series_id is not None:
            stmt = stmt.where(self.model.series_id == series_id)
        if name is not None:
            stmt = stmt.where(self.model.name.like(f'%{name}%'))
        if nfc_code is not None:
            stmt = stmt.join(ToyNfc, ToyNfc.toy_id == self.model.id).where(
                ToyNfc.deleted == 0,
                ToyNfc.status == 1,
                ToyNfc.nfc_code == nfc_code,
            )
        if voice_language is not None:
            stmt = stmt.where(self.model.voice_language == voice_language)
        if status is not None:
            stmt = stmt.where(self.model.status == status)

        return stmt.order_by(self.model.sort.asc(), self.model.id.desc())

    async def create(self, db: AsyncSession, obj: CreateToyParam) -> Toy:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateToyParam | dict[str, Any]) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id=pk)


class CRUDToyNfc(CRUDPlus[ToyNfc]):
    async def get(self, db: AsyncSession, pk: int) -> ToyNfc | None:
        stmt = sa.select(self.model).where(self.model.deleted == 0, self.model.id == pk).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, db: AsyncSession, *, nfc_code: str) -> ToyNfc | None:
        stmt = sa.select(self.model).where(
            self.model.deleted == 0,
            self.model.nfc_code == nfc_code,
        ).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_codes(self, db: AsyncSession, *, nfc_codes: Sequence[str]) -> Sequence[ToyNfc]:
        if not nfc_codes:
            return []
        stmt = sa.select(self.model).where(
            self.model.deleted == 0,
            self.model.nfc_code.in_(nfc_codes),
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_by_toy_id(self, db: AsyncSession, *, toy_id: int) -> Sequence[ToyNfc]:
        stmt = (
            sa.select(self.model)
            .where(self.model.deleted == 0, self.model.toy_id == toy_id)
            .order_by(self.model.id.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_select(
        self,
        *,
        toy_id: int | None,
        nfc_code: str | None,
        status: int | None,
    ) -> Select:
        stmt = sa.select(self.model).where(self.model.deleted == 0)
        if toy_id is not None:
            stmt = stmt.where(self.model.toy_id == toy_id)
        if nfc_code is not None:
            stmt = stmt.where(self.model.nfc_code == nfc_code)
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        return stmt.order_by(self.model.created_time.desc(), self.model.id.desc())

    async def create(self, db: AsyncSession, obj: CreateToyNfcParam) -> ToyNfc:
        return await self.create_model(db, obj, flush=True)

    async def create_batch(
        self,
        db: AsyncSession,
        *,
        toy_id: int,
        nfc_codes: Sequence[str],
        batch_no: str | None,
        status: int,
        remark: str | None,
    ) -> Sequence[ToyNfc]:
        bindings = [
            self.model(
                toy_id=toy_id,
                nfc_code=nfc_code,
                batch_no=batch_no,
                status=status,
                remark=remark,
            )
            for nfc_code in nfc_codes
        ]
        db.add_all(bindings)
        await db.flush()
        return bindings

    async def update(self, db: AsyncSession, pk: int, obj: UpdateToyNfcParam | dict[str, Any]) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, *, pk: int, toy_id: int) -> int:
        result = await db.execute(
            sa.delete(self.model).where(self.model.id == pk, self.model.toy_id == toy_id)
        )
        return result.rowcount or 0


toy_series_dao: CRUDToySeries = CRUDToySeries(ToySeries)
toy_dao: CRUDToy = CRUDToy(Toy)
toy_nfc_dao: CRUDToyNfc = CRUDToyNfc(ToyNfc)
