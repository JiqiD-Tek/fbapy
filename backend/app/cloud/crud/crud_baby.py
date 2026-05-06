from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import Baby, Device
from backend.app.cloud.schema.baby import CreateBabyData, UpdateBabyParam


class CRUDBaby(CRUDPlus[Baby]):
    async def get(self, db: AsyncSession, pk: int) -> Baby | None:
        return await self.select_model(db, pk)

    async def get_by_device_did(self, db: AsyncSession, *, did: str) -> Baby | None:
        stmt = (
            select(Baby)
            .join(Device, Device.id == Baby.device_id)
            .where(Device.did == did)
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_select(
            self,
            *,
            user_id: int,
            name: str | None = None,
            nickname: str | None = None,
            sex: int | None = None,
            device_id: int | None = None,
    ) -> Select:
        stmt = select(Baby).where(Baby.user_id == user_id)

        if device_id is not None:
            stmt = stmt.where(Baby.device_id == device_id)
        if name is not None:
            stmt = stmt.where(Baby.name.like(f'%{name}%'))
        if nickname is not None:
            stmt = stmt.where(Baby.nickname.like(f'%{nickname}%'))
        if sex is not None:
            stmt = stmt.where(Baby.sex == sex)

        return stmt.distinct().order_by(Baby.id.desc())

    async def get_all_by_user(self, db: AsyncSession, *, user_id: int) -> Sequence[Baby]:
        stmt = (
            select(Baby)
            .where(Baby.user_id == user_id)
            .distinct()
            .order_by(Baby.id.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_all_by_device(self, db: AsyncSession, *, user_id: int, device_id: int) -> Sequence[Baby]:
        stmt = (
            select(Baby)
            .where(Baby.user_id == user_id, Baby.device_id == device_id)
            .distinct()
            .order_by(Baby.id.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create(self, db: AsyncSession, obj: CreateBabyData) -> Baby:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateBabyParam) -> int:
        return await self.update_model(db, pk, obj)


baby_dao: CRUDBaby = CRUDBaby(Baby)
