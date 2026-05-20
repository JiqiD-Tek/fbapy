from collections.abc import Sequence

from datetime import datetime

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import FirmwareWhitelist
from backend.app.cloud.schema.firmware import CreateFirmwareWhitelistParam, UpdateFirmwareWhitelistParam


class CRUDFirmwareWhitelist(CRUDPlus[FirmwareWhitelist]):
    async def get(self, db: AsyncSession, pk: int) -> FirmwareWhitelist | None:
        return await self.select_model(db, pk)

    async def get_select(
        self,
        *,
        firmware_id: int | None = None,
        device_did: str | None = None,
        enabled: bool | None = None,
    ) -> Select:
        stmt = select(FirmwareWhitelist)

        if firmware_id is not None:
            stmt = stmt.where(FirmwareWhitelist.firmware_id == firmware_id)
        if device_did is not None:
            stmt = stmt.where(FirmwareWhitelist.device_did == device_did)
        if enabled is not None:
            stmt = stmt.where(FirmwareWhitelist.enabled == enabled)

        return stmt.order_by(FirmwareWhitelist.id.desc())

    async def get_by_device_did(self, db: AsyncSession, device_did: str) -> FirmwareWhitelist | None:
        return await self.select_model_by_column(db, device_did=device_did)

    async def get_by_device_dids(self, db: AsyncSession, device_dids: list[str]) -> Sequence[FirmwareWhitelist]:
        if not device_dids:
            return []
        return await self.select_models(db, FirmwareWhitelist.device_did.in_(device_dids))

    async def get_active_by_device_did(
        self,
        db: AsyncSession,
        *,
        device_did: str,
        now: datetime,
    ) -> FirmwareWhitelist | None:
        stmt = (
            select(FirmwareWhitelist)
            .where(
                FirmwareWhitelist.device_did == device_did,
                FirmwareWhitelist.enabled.is_(True),
                or_(FirmwareWhitelist.expires_at.is_(None), FirmwareWhitelist.expires_at > now),
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, obj: CreateFirmwareWhitelistParam) -> FirmwareWhitelist:
        return await self.create_model(db, obj, flush=True)

    async def count_by_firmware_id(self, db: AsyncSession, firmware_id: int) -> int:
        return await self.count(db, FirmwareWhitelist.firmware_id == firmware_id)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateFirmwareWhitelistParam | dict) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id=pk)


firmware_whitelist_dao: CRUDFirmwareWhitelist = CRUDFirmwareWhitelist(FirmwareWhitelist)
