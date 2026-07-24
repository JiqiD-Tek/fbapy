from collections.abc import Sequence

from datetime import datetime
from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import Firmware
from backend.app.cloud.model import FirmwareWhitelist
from backend.app.cloud.schema.firmware import CreateFirmwareParam, FirmwareReleaseScope, UpdateFirmwareParam
from backend.app.cloud.schema.firmware import CreateFirmwareWhitelistParam, UpdateFirmwareWhitelistParam


class CRUDFirmware(CRUDPlus[Firmware]):
    async def get(self, db: AsyncSession, pk: int) -> Firmware | None:
        return await self.select_model(db, pk)

    async def get_select(
            self,
            name: str | None,
            version: str | None,
            device_model: str | None,
            status: int | None,
            is_latest: bool | None,
            release_scope: FirmwareReleaseScope | None,
    ) -> Select:
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
        if release_scope is not None:
            filters['release_scope'] = release_scope

        return await self.select_order('id', 'desc', **filters)

    async def get_by_name(self, db: AsyncSession, name: str) -> Firmware | None:
        return await self.select_model_by_column(db, name=name)

    async def get_by_version(self, db: AsyncSession, version: str) -> Firmware | None:
        return await self.select_model_by_column(db, version=version)

    async def get_by_device_model(self, db: AsyncSession, device_model: str) -> Sequence[Firmware]:
        return await self.select_models(db, device_model=device_model)

    async def get_latest_firmware(self, db: AsyncSession, device_model: str) -> Firmware | None:
        return await self.select_model_by_column(db, device_model=device_model, is_latest=True, status=1)

    async def get_public_upgrade_firmware(self, db: AsyncSession, *, device_model: str,
                                          version_code: int) -> Firmware | None:
        stmt = (
            select(Firmware)
            .where(
                Firmware.device_model == device_model,
                Firmware.status == 1,
                Firmware.release_scope == FirmwareReleaseScope.PUBLIC.value,
                Firmware.version_code > version_code,
            )
            .order_by(Firmware.version_code.desc(), Firmware.id.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, db: AsyncSession) -> Sequence[Firmware]:
        return await self.select_models(db)

    async def create(self, db: AsyncSession, obj: CreateFirmwareParam) -> Firmware:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateFirmwareParam) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id=pk)

    async def delete_by_pks(self, db: AsyncSession, pks: list[int]) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def increment_download_count(self, db: AsyncSession, pk: int) -> int:
        firmware = await self.get(db, pk)
        if firmware:
            return await self.update_model(db, pk, {'download_count': firmware.download_count + 1})
        return 0


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


firmware_dao: CRUDFirmware = CRUDFirmware(Firmware)
firmware_whitelist_dao: CRUDFirmwareWhitelist = CRUDFirmwareWhitelist(FirmwareWhitelist)
