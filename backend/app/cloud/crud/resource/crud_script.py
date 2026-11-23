from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import Script
from backend.app.cloud.schema.resource.script import CreateScriptParam, UpdateScriptParam


class CRUDScript(CRUDPlus[Script]):
    async def get(self, db: AsyncSession, pk: int) -> Script | None:
        return await self.select_model(db, pk)

    async def get_select(
        self,
        title: str | None,
        author: str | None,
        status: int | None,
        baby_id: int | None = None,
        favorite: int | None = None,
        album_id: int | None = None,
        content_types: list[int] | None = None,
    ) -> Select:
        filters = {}

        if title is not None:
            filters['title__like'] = f'%{title}%'
        if author is not None:
            filters['author__like'] = f'%{author}%'
        if status is not None:
            filters['status'] = status
        if baby_id is not None:
            filters['baby_id'] = baby_id
        if favorite is not None:
            filters['favorite'] = favorite
        if album_id is not None:
            filters['album_id'] = album_id

        stmt = await self.select_order('id', 'desc', **filters)

        if content_types:
            stmt = stmt.where(self._build_json_array_contains_condition(self.model.content_types, content_types))
        return stmt

    async def create(self, db: AsyncSession, obj: CreateScriptParam) -> Script:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateScriptParam | dict) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id=pk)

    async def count_by_album_id(self, db: AsyncSession, album_id: int) -> int:
        return await self.count(db, album_id=album_id)

    async def get_generated_topics_by_time_range(
            self,
            db: AsyncSession,
            *,
            baby_id: int,
            start_time: datetime,
            end_time: datetime,
            limit: int | None = None,
    ) -> Sequence[tuple[datetime, str | None]]:
        stmt = (
            sa.select(self.model.created_time, self.model.remark)
            .where(
                self.model.deleted == 0,
                self.model.baby_id == baby_id,
                self.model.created_time >= start_time,
                self.model.created_time < end_time,
            )
            .order_by(self.model.created_time.desc(), self.model.id.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return result.tuples().all()

script_dao: CRUDScript = CRUDScript(Script)
