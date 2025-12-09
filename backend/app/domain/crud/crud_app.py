from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.domain.model import App
from backend.app.domain.schema.app import CreateAppParam, UpdateAppParam


class CRUDApp(CRUDPlus[App]):

    async def get(self, db: AsyncSession, pk: int) -> App | None:
        return await self.select_model(db, pk)

    async def get_select(self, name: str | None, package_name: str | None, status: int | None) -> Select:
        filters = {}

        if name is not None:
            filters['name'] = name
        if package_name is not None:
            filters['package_name'] = package_name
        if status is not None:
            filters['status'] = status
        return await self.select_order('id', **filters)

    async def get_by_name(self, db: AsyncSession, name: str) -> App | None:
        return await self.select_model_by_column(db, name=name)

    async def get_all(self, db: AsyncSession) -> Sequence[App]:
        return await self.select_models(db)

    async def create(self, db: AsyncSession, obj: CreateAppParam) -> None:
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateAppParam) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)


app_dao: CRUDApp = CRUDApp(App)
