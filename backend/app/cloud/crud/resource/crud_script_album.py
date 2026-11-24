import json

import sqlalchemy as sa
from sqlalchemy import Select, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import Script, ScriptAlbum
from backend.app.cloud.schema.resource.script_album import CreateScriptAlbumParam, UpdateScriptAlbumParam
from backend.common.enums import DataBaseType
from backend.core.conf import settings


class CRUDScriptAlbum(CRUDPlus[ScriptAlbum]):
    async def get(self, db: AsyncSession, pk: int) -> ScriptAlbum | None:
        return await self.select_model(db, pk)

    async def get_by_exact_toy_ids(self, db: AsyncSession, toy_ids: list[int]) -> ScriptAlbum | None:
        stmt = await self.get_select(title=None, author=None, status=None, exact_toy_ids=toy_ids)
        stmt = stmt.where(self.model.deleted == 0).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_select(
            self,
            title: str | None,
            author: str | None,
            status: int | None,
            resource_type: int | None = None,
            exact_toy_ids: list[int] | None = None,
    ) -> Select:
        filters = {}
        if title is not None:
            filters['title__like'] = f'%{title}%'
        if author is not None:
            filters['author__like'] = f'%{author}%'
        if status is not None:
            filters['status'] = status
        if resource_type is not None:
            filters['resource_type'] = resource_type
        stmt = await self.select_order('id', 'desc', **filters)
        if exact_toy_ids:
            stmt = stmt.where(self._build_exact_toy_ids_condition(exact_toy_ids))
        return stmt

    @staticmethod
    def _build_exact_toy_ids_condition(toy_ids: list[int]) -> sa.ColumnElement[bool]:
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

    async def create(self, db: AsyncSession, obj: CreateScriptAlbumParam) -> ScriptAlbum:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateScriptAlbumParam | dict) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id=pk)

    async def get_script_contents(self, db: AsyncSession, album_id: int) -> list[list[dict]]:
        result = await db.execute(select(Script.content).where(Script.album_id == album_id, Script.deleted == 0))
        return list(result.scalars().all())

script_album_dao: CRUDScriptAlbum = CRUDScriptAlbum(ScriptAlbum)
