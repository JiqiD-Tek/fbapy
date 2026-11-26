from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import DeviceUsage, DeviceUsageEvent


class CRUDDeviceUsage(CRUDPlus[DeviceUsage]):
    async def get(
            self, db: AsyncSession, *, did: str, usage_date: date,
    ) -> DeviceUsage | None:
        result = await db.execute(
            select(self.model)
            .where(self.model.did == did, self.model.usage_date == usage_date)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_for_update(
            self, db: AsyncSession, *, did: str, usage_date: date,
    ) -> DeviceUsage | None:
        result = await db.execute(
            select(self.model)
            .where(self.model.did == did, self.model.usage_date == usage_date)
            .with_for_update()
            .limit(1)
        )
        return result.scalar_one_or_none()


class CRUDDeviceUsageEvent(CRUDPlus[DeviceUsageEvent]):
    async def get_by_business(
            self, db: AsyncSession, *, event_type: str, event_key: str,
    ) -> DeviceUsageEvent | None:
        result = await db.execute(
            select(self.model)
            .where(self.model.event_type == event_type, self.model.event_key == event_key)
            .limit(1)
        )
        return result.scalar_one_or_none()


device_usage_dao = CRUDDeviceUsage(DeviceUsage)
device_usage_event_dao = CRUDDeviceUsageEvent(DeviceUsageEvent)
