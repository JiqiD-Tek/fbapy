from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.iot.model import DeviceUsage
from backend.app.iot.schema.device.device_usage import CreateDeviceUsageParam, UpdateDeviceUsageParam, UsageStatus


class CRUDDeviceUsage(CRUDPlus[DeviceUsage]):
    async def get(self, db: AsyncSession, pk: int) -> DeviceUsage | None:
        return await self.select_model(db, pk)

    async def get_by_did(self, db: AsyncSession, did: str) -> Sequence[DeviceUsage]:
        return await self.select_models(db, did=did)

    async def get_by_did_status(self, db: AsyncSession, did: str, status: UsageStatus) -> Sequence[DeviceUsage]:
        return await self.select_models(db, did=did, status=status)

    async def create(self, db: AsyncSession, obj: CreateDeviceUsageParam) -> DeviceUsage:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateDeviceUsageParam) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)


device_usage_dao: CRUDDeviceUsage = CRUDDeviceUsage(DeviceUsage)
