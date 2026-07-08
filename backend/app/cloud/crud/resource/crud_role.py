# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : crud_role.py
@Author  : OpenAI
@Date    : 2026/07/06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import CloudRole
from backend.app.cloud.schema.resource.role import CreateRoleParam, UpdateRoleParam


class CRUDCloudRole(CRUDPlus[CloudRole]):
    async def get(self, db: AsyncSession, pk: int) -> CloudRole | None:
        return await self.select_model(db, pk)

    async def get_by_role_key(self, db: AsyncSession, *, role_key: str) -> CloudRole | None:
        return await self.select_model_by_column(db, role_key=role_key)

    async def get_select(
        self,
        *,
        role_key: str | None,
        group_key: str | None,
        name: str | None,
        voice_language: str | None,
        status: int | None,
    ) -> Select:
        stmt = sa.select(self.model).where(self.model.deleted == 0)

        if role_key is not None:
            stmt = stmt.where(self.model.role_key.like(f'%{role_key}%'))
        if group_key is not None:
            stmt = stmt.where(self.model.group_key == group_key)
        if name is not None:
            stmt = stmt.where(self.model.name.like(f'%{name}%'))
        if voice_language is not None:
            stmt = stmt.where(self.model.voice_language == voice_language)
        if status is not None:
            stmt = stmt.where(self.model.status == status)

        return stmt.order_by(self.model.sort.asc(), self.model.id.desc())

    async def get_enabled(
        self,
        db: AsyncSession,
        *,
        group_key: str | None = None,
        voice_language: str | None = None,
    ) -> Sequence[CloudRole]:
        stmt = sa.select(self.model).where(self.model.deleted == 0, self.model.status == 1)
        if group_key is not None:
            stmt = stmt.where(self.model.group_key == group_key)
        if voice_language is not None:
            stmt = stmt.where(self.model.voice_language == voice_language)
        stmt = stmt.order_by(self.model.sort.asc(), self.model.id.desc())
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create(self, db: AsyncSession, obj: CreateRoleParam | dict) -> CloudRole:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateRoleParam | dict) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id=pk)


cloud_role_dao: CRUDCloudRole = CRUDCloudRole(CloudRole)
