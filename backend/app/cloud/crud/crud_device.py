from datetime import date, datetime
from typing import Any
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import Device
from backend.app.cloud.model import DeviceChat
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


class CRUDDeviceChat(CRUDPlus[DeviceChat]):
    async def get(self, db: AsyncSession, pk: int) -> DeviceChat | None:
        return await self.select_model(db, pk)

    async def get_select(
            self,
            *,
            device_id: int | None = None,
            user_id: int | None = None,
            baby_id: int | None = None,
    ) -> Select:
        stmt = sa.select(self.model).where(self.model.deleted == 0)

        if device_id is not None:
            stmt = stmt.where(self.model.device_id == device_id)
        if user_id is not None:
            stmt = stmt.where(self.model.user_id == user_id)
        if baby_id is not None:
            stmt = stmt.where(self.model.baby_id == baby_id)

        return stmt.order_by(self.model.created_time.desc(), self.model.id.desc())

    async def create(self, db: AsyncSession, obj: dict[str, Any] | DeviceChat) -> DeviceChat:
        record = self.model(**obj) if isinstance(obj, dict) else obj
        db.add(record)
        await db.flush()
        return record

    async def get_daily_chat_counts(
            self,
            db: AsyncSession,
            *,
            baby_id: int,
            start_time: datetime,
            end_time: datetime,
    ) -> dict[date, int]:
        chat_date = func.date(self.model.created_time)
        stmt = (
            select(chat_date, func.count())
            .where(
                self.model.deleted == 0,
                self.model.baby_id == baby_id,
                self.model.created_time >= start_time,
                self.model.created_time < end_time,
            )
            .group_by(chat_date)
        )
        result = await db.execute(stmt)

        daily_counts: dict[date, int] = {}
        for raw_chat_date, chat_count in result.all():
            if isinstance(raw_chat_date, datetime):
                chat_day = raw_chat_date.date()
            elif isinstance(raw_chat_date, date):
                chat_day = raw_chat_date
            else:
                chat_day = date.fromisoformat(str(raw_chat_date))

            daily_counts[chat_day] = int(chat_count)

        return daily_counts


device_dao: CRUDDevice = CRUDDevice(Device)
device_chat_dao: CRUDDeviceChat = CRUDDeviceChat(DeviceChat)
