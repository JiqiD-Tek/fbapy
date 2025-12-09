from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.domain.model import Device
from backend.app.domain.schema.device import CreateDeviceParam, UpdateDeviceParam


class CRUDDevice(CRUDPlus[Device]):

    async def get(self, db: AsyncSession, pk: int) -> Device | None:
        return await self.select_model(db, pk)

    async def get_select(self, did: str | None, sn: str | None, mac: str | None, model: str | None,
                         user_id: int | None) -> Select:
        filters = {}

        if did is not None:
            filters['did'] = did
        if sn is not None:
            filters['sn'] = sn
        if mac is not None:
            filters['mac'] = mac
        if model is not None:
            filters['model'] = model
        if user_id is not None:
            filters['user_id'] = user_id

        return await self.select_order('id', **filters)

    async def get_by_did(self, db: AsyncSession, did: str) -> Device | None:
        return await self.select_model_by_column(db, did=did)

    async def get_by_sn(self, db: AsyncSession, sn: str) -> Device | None:
        return await self.select_model_by_column(db, sn=sn)

    async def get_by_mac(self, db: AsyncSession, mac: str) -> Device | None:
        return await self.select_model_by_column(db, mac=mac)

    async def get_by_user_id(self, db: AsyncSession, user_id: int) -> Sequence[Device]:
        return await self.select_models(db, user_id=user_id)

    async def get_by_model(self, db: AsyncSession, model: str) -> Sequence[Device]:
        return await self.select_models(db, model=model)

    async def get_all(self, db: AsyncSession) -> Sequence[Device]:
        return await self.select_models(db)

    async def create(self, db: AsyncSession, obj: CreateDeviceParam) -> None:
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateDeviceParam) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def update_firmware_version(self, db: AsyncSession, pk: int, firmware_version: str) -> int:
        return await self.update_model(db, pk, {'firmware': firmware_version})

    async def update_user_id(self, db: AsyncSession, pk: int, user_id: int) -> int:
        return await self.update_model(db, pk, {'user_id': user_id})

    async def get_device_count_by_model(self, db: AsyncSession, model: str) -> int:
        return await self.count(db, model=model)

    async def get_device_count_by_user(self, db: AsyncSession, user_id: int) -> int:
        return await self.count(db, user_id=user_id)


device_dao: CRUDDevice = CRUDDevice(Device)
