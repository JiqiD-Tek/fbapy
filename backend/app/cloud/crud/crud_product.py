# -*- coding: UTF-8 -*-
"""商城商品数据访问层。"""

from typing import Any

import sqlalchemy as sa

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import Product


class CRUDProduct(CRUDPlus[Product]):
    """商城商品 CRUD。"""

    async def get(self, db: AsyncSession, pk: int) -> Product | None:
        stmt = sa.select(self.model).where(self.model.deleted == 0, self.model.id == pk).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_select(
            self,
            *,
            parent_id: int | None,
            ref_type: str | None,
            ref_id: int | None,
            name: str | None,
            status: int | None,
    ) -> Select:
        stmt = sa.select(self.model).where(self.model.deleted == 0)
        if parent_id is not None:
            stmt = stmt.where(self.model.parent_id == parent_id)
        if ref_type is not None:
            stmt = stmt.where(self.model.ref_type == ref_type)
        if ref_id is not None:
            stmt = stmt.where(self.model.ref_id == ref_id)
        if name is not None:
            stmt = stmt.where(self.model.name.like(f'%{name}%'))
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        return stmt.order_by(self.model.sort.asc(), self.model.id.desc())

    async def has_children(self, db: AsyncSession, *, parent_id: int) -> bool:
        stmt = sa.select(self.model.id).where(
            self.model.deleted == 0,
            self.model.parent_id == parent_id,
        ).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create(self, db: AsyncSession, obj: Any) -> Product:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: dict[str, Any]) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id=pk)


product_dao = CRUDProduct(Product)
