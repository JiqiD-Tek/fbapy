import json

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import Script, ScriptAlbum
from backend.app.cloud.schema.resource.script import CreateScriptParam, UpdateScriptParam
from backend.common.enums import DataBaseType
from backend.core.conf import settings


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
        toy_ids: list[int] | None = None,
        exact_toy_ids: list[int] | None = None,
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
        if toy_ids:
            stmt = stmt.join(ScriptAlbum, ScriptAlbum.id == self.model.album_id)
            stmt = stmt.where(self._build_contains_toy_ids_condition(toy_ids))
        if exact_toy_ids:
            if not toy_ids:
                stmt = stmt.join(ScriptAlbum, ScriptAlbum.id == self.model.album_id)
            stmt = stmt.where(self._build_exact_toy_ids_condition(exact_toy_ids))

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

    def _build_contains_toy_ids_condition(self, toy_ids: list[int]) -> sa.ColumnElement[bool]:
        return self._build_json_array_contains_condition(ScriptAlbum.toy_ids, toy_ids)

    @staticmethod
    def _build_json_array_contains_condition(
            column: InstrumentedAttribute,
            values: list[int],
    ) -> sa.ColumnElement[bool]:
        if settings.DATABASE_TYPE == DataBaseType.postgresql:
            json_array = sa.cast(column, postgresql.JSONB)
            return json_array.contains(values)
        return sa.func.JSON_CONTAINS(column, json.dumps(values)) == 1

    def _build_exact_toy_ids_condition(self, toy_ids: list[int]) -> sa.ColumnElement[bool]:
        if settings.DATABASE_TYPE == DataBaseType.postgresql:
            toy_ids_expr = sa.cast(ScriptAlbum.toy_ids, postgresql.JSONB)
            return sa.and_(
                toy_ids_expr.contains(toy_ids),
                sa.func.jsonb_array_length(toy_ids_expr) == len(toy_ids),
            )
        return sa.and_(
            sa.func.JSON_CONTAINS(ScriptAlbum.toy_ids, json.dumps(toy_ids)) == 1,
            sa.func.JSON_LENGTH(ScriptAlbum.toy_ids) == len(toy_ids),
        )


script_dao: CRUDScript = CRUDScript(Script)
