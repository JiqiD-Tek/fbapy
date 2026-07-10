import json

import sqlalchemy as sa
from sqlalchemy import Select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import CloudScript
from backend.app.cloud.schema.resource.script import CreateScriptParam, UpdateScriptParam
from backend.common.enums import DataBaseType
from backend.core.conf import settings


class CRUDCloudScript(CRUDPlus[CloudScript]):
    async def get(self, db: AsyncSession, pk: int) -> CloudScript | None:
        return await self.select_model(db, pk)

    async def get_select(
            self,
            title: str | None,
            author: str | None,
            status: int | None,
            role_ids: list[int] | None = None,
            exact_role_ids: list[int] | None = None,
    ) -> Select:
        filters = {}

        if title is not None:
            filters['title__like'] = f'%{title}%'
        if author is not None:
            filters['author__like'] = f'%{author}%'
        if status is not None:
            filters['status'] = status

        stmt = await self.select_order('id', 'desc', **filters)

        if role_ids:
            stmt = stmt.where(self._build_contains_role_ids_condition(role_ids))
        if exact_role_ids:
            stmt = stmt.where(self._build_exact_role_ids_condition(exact_role_ids))

        return stmt

    async def create(self, db: AsyncSession, obj: CreateScriptParam) -> CloudScript:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateScriptParam | dict) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id=pk)

    def _build_contains_role_ids_condition(self, role_ids: list[int]) -> sa.ColumnElement[bool]:
        if settings.DATABASE_TYPE == DataBaseType.postgresql:
            role_ids_expr = sa.cast(self.model.role_ids, postgresql.JSONB)
            return role_ids_expr.contains(role_ids)
        return sa.func.JSON_CONTAINS(self.model.role_ids, json.dumps(role_ids)) == 1

    def _build_exact_role_ids_condition(self, role_ids: list[int]) -> sa.ColumnElement[bool]:
        if settings.DATABASE_TYPE == DataBaseType.postgresql:
            role_ids_expr = sa.cast(self.model.role_ids, postgresql.JSONB)
            return sa.and_(
                role_ids_expr.contains(role_ids),
                sa.func.jsonb_array_length(role_ids_expr) == len(role_ids),
            )
        return sa.and_(
            sa.func.JSON_CONTAINS(self.model.role_ids, json.dumps(role_ids)) == 1,
            sa.func.JSON_LENGTH(self.model.role_ids) == len(role_ids),
        )


cloud_script_dao: CRUDCloudScript = CRUDCloudScript(CloudScript)
