from typing import Any

import sqlalchemy as sa

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import DeviceChat


class CRUDDeviceChat(CRUDPlus[DeviceChat]):
    async def get(self, db: AsyncSession, pk: int) -> DeviceChat | None:
        return await self.select_model(db, pk)

    async def get_select(
            self,
            *,
            device_id: int | None = None,
            toy_id: int | None = None,
            user_id: int | None = None,
            baby_id: int | None = None,
    ) -> Select:
        stmt = sa.select(self.model).where(self.model.deleted == 0)

        if device_id is not None:
            stmt = stmt.where(self.model.device_id == device_id)
        if toy_id is not None:
            stmt = stmt.where(self.model.toy_id == toy_id)
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


device_chat_dao: CRUDDeviceChat = CRUDDeviceChat(DeviceChat)
