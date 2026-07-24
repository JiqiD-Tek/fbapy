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

from backend.app.cloud.model import Toy
from backend.app.cloud.schema.device.toy import CreateToyParam, UpdateToyParam


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
        stmt = sa.select(self.model).where(self.model.deleted == 0, self.model.nfc_code == nfc_code)
        if enabled_only:
            stmt = stmt.where(self.model.status == 1)
        result = await db.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def get_select(
        self,
        *,
        series_name: str | None,
        name: str | None,
        nfc_code: str | None,
        voice_language: str | None,
        status: int | None,
    ) -> Select:
        stmt = sa.select(self.model).where(self.model.deleted == 0)

        if series_name is not None:
            stmt = stmt.where(self.model.series_name == series_name)
        if name is not None:
            stmt = stmt.where(self.model.name.like(f'%{name}%'))
        if nfc_code is not None:
            stmt = stmt.where(self.model.nfc_code == nfc_code)
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


toy_dao: CRUDToy = CRUDToy(Toy)
