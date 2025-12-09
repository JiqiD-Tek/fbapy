from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.domain.model import Firmware
from backend.app.domain.schema.firmware import CreateFirmwareParam, UpdateFirmwareParam


class CRUDFirmware(CRUDPlus[Firmware]):

    async def get(self, db: AsyncSession, pk: int) -> Firmware | None:
        return await self.select_model(db, pk)

    async def get_select(self, name: str | None, version: str | None, device_model: str | None, status: int | None,
                         is_latest: bool | None) -> Select:
        filters = {}

        if name is not None:
            filters['name__like'] = f'%{name}%'
        if version is not None:
            filters['version'] = version
        if device_model is not None:
            filters['device_model'] = device_model
        if status is not None:
            filters['status'] = status
        if is_latest is not None:
            filters['is_latest'] = is_latest

        return await self.select_order('id', **filters)

    async def get_by_name(self, db: AsyncSession, name: str) -> Firmware | None:
        return await self.select_model_by_column(db, name=name)

    async def get_by_version(self, db: AsyncSession, version: str) -> Firmware | None:
        return await self.select_model_by_column(db, version=version)

    async def get_by_device_model(self, db: AsyncSession, device_model: str) -> Sequence[Firmware]:
        return await self.select_models(db, device_model=device_model)

    async def get_latest_firmware(self, db: AsyncSession, device_model: str) -> Firmware | None:
        return await self.select_model_by_column(db, device_model=device_model, is_latest=True, status=1)

    async def get_all(self, db: AsyncSession) -> Sequence[Firmware]:
        return await self.select_models(db)

    async def create(self, db: AsyncSession, obj: CreateFirmwareParam) -> None:
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateFirmwareParam) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def increment_download_count(self, db: AsyncSession, pk: int) -> int:
        firmware = await self.get(db, pk)
        if firmware:
            return await self.update_model(db, pk, {'download_count': firmware.download_count + 1})
        return 0


firmware_dao: CRUDFirmware = CRUDFirmware(Firmware)
