from collections.abc import Sequence

from sqlalchemy import Select, case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import App
from backend.app.cloud.schema.app import CreateAppParam, UpdateAppParam


class CRUDApp(CRUDPlus[App]):
    async def get(self, db: AsyncSession, pk: int) -> App | None:
        return await self.select_model(db, pk)

    async def get_select(
        self,
        name: str | None,
        package_name: str | None,
        market_code: str | None,
        status: int | None,
    ) -> Select:
        filters = {
            key: value
            for key, value in {
                'name': name,
                'package_name': package_name,
                'market_code': market_code,
                'status': status,
            }.items()
            if value is not None
        }
        return await self.select_order('id', 'desc', **filters)

    async def get_by_name(self, db: AsyncSession, name: str) -> App | None:
        return await self.select_model_by_column(db, name=name)

    async def get_upgrade_app(
        self,
        db: AsyncSession,
        *,
        package_name: str,
        market_code: str | None,
        version_code: int,
    ) -> App | None:
        """Return the highest enabled version newer than the client version."""
        stmt = select(App).where(
            App.package_name == package_name,
            App.status == 1,
            App.version_code > version_code,
        )
        if market_code is None:
            stmt = stmt.where(App.market_code.is_(None))
            stmt = stmt.order_by(App.version_code.desc(), App.id.desc())
        else:
            # A regional release wins over the global release at the same version.
            stmt = stmt.where(or_(App.market_code == market_code, App.market_code.is_(None)))
            stmt = stmt.order_by(
                App.version_code.desc(),
                case((App.market_code == market_code, 0), else_=1),
                App.id.desc(),
            )
        stmt = stmt.limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, db: AsyncSession) -> Sequence[App]:
        return await self.select_models(db)

    async def create(self, db: AsyncSession, obj: CreateAppParam) -> App:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateAppParam) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id=pk)


app_dao: CRUDApp = CRUDApp(App)
