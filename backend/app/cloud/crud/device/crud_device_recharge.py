from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import DeviceRecharge
from backend.app.cloud.schema.device.device_recharge import CreateDeviceRechargeParam, UpdateDeviceRechargeParam


class CRUDDeviceRecharge(CRUDPlus[DeviceRecharge]):
    async def get(self, db: AsyncSession, pk: int) -> DeviceRecharge | None:
        return await self.select_model(db, pk)

    async def get_by_device_did(self, db: AsyncSession, device_did: str) -> Sequence[DeviceRecharge]:
        return await self.select_models(db, device_did=device_did)

    async def create(self, db: AsyncSession, obj: CreateDeviceRechargeParam) -> DeviceRecharge:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateDeviceRechargeParam) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)


device_recharge_dao: CRUDDeviceRecharge = CRUDDeviceRecharge(DeviceRecharge)
