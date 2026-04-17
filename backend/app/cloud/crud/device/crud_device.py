from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import Device
from backend.app.cloud.model.m2m import user_device
from backend.app.cloud.schema.device.device import CreateDeviceParam, UpdateDeviceParam


class CRUDDevice(CRUDPlus[Device]):
    async def get(self, db: AsyncSession, pk: int) -> Device | None:
        return await self.select_model(db, pk)

    async def get_select(
        self,
        *,
        user_id: int | None = None,
        did: str | None = None,
        sn: str | None = None,
        mac: str | None = None,
        model: str | None = None,
    ) -> Select:
        stmt = select(Device)

        if user_id is not None:
            stmt = stmt.join(user_device, user_device.c.device_id == Device.id).where(user_device.c.user_id == user_id)
        if did is not None:
            stmt = stmt.where(Device.did == did)
        if sn is not None:
            stmt = stmt.where(Device.sn == sn)
        if mac is not None:
            stmt = stmt.where(Device.mac == mac)
        if model is not None:
            stmt = stmt.where(Device.model == model)

        return stmt.distinct().order_by(Device.id.desc())

    async def get_by_did(self, db: AsyncSession, did: str) -> Device | None:
        return await self.select_model_by_column(db, did=did)

    async def get_by_model(self, db: AsyncSession, model: str) -> Sequence[Device]:
        return await self.select_models(db, Device.model == model)

    async def get_all(self, db: AsyncSession) -> Sequence[Device]:
        return await self.select_models(db)

    async def create(self, db: AsyncSession, obj: CreateDeviceParam) -> Device:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateDeviceParam) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id=pk)

    async def update_firmware_version(self, db: AsyncSession, pk: int, firmware_version: str) -> int:
        return await self.update_model(db, pk, {'firmware': firmware_version})

    async def get_device_count_by_model(self, db: AsyncSession, model: str) -> int:
        return await self.count(db, Device.model == model)

    async def get_device_count_by_user(self, db: AsyncSession, user_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(user_device)
            .where(user_device.c.user_id == user_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one()


device_dao: CRUDDevice = CRUDDevice(Device)
