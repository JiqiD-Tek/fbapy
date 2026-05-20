# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device_service.py
@Author  : guhua@jiqid.com
@Date    : 2025/12/09 13:50
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.device.crud_device import device_dao
from backend.app.cloud.crud.device.crud_device_usage import device_usage_dao
from backend.app.cloud.model import Baby, Device
from backend.app.cloud.model.m2m import user_device
from backend.app.cloud.schema.device.device import UpdateDeviceParam
from backend.app.cloud.schema.device.device_usage import CreateDeviceUsageParam, UpdateDeviceUsageParam, UsageStatus
from backend.app.cloud.timeseries.state_store import StateStore
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.common.response.response_code import CustomErrorCode
from backend.utils.timezone import timezone

MAX_ALLOW_QUOTA = 600


class DeviceService:
    """Device service"""

    async def allocate_quota(self, db: AsyncSession, did: str) -> int:
        device = await self.get_by_did(db=db, did=did)

        quota = await self._settle_active_usages(db=db, device=device)
        if quota <= 0:
            raise errors.CustomError(error=CustomErrorCode.DEVICE_QUOTA_NOT_ENOUGH)

        alloc_quota = min(quota, MAX_ALLOW_QUOTA)
        if alloc_quota <= 0:
            raise errors.CustomError(error=CustomErrorCode.DEVICE_QUOTA_NOT_ENOUGH)

        usage = CreateDeviceUsageParam.model_construct(
            device_did=did,
            apply_quota=alloc_quota,
            start_time=timezone.now(),
        )
        await device_usage_dao.create(db, usage)

        return alloc_quota

    async def end_usage(self, db: AsyncSession, did: str) -> int:
        device = await self.get_by_did(db=db, did=did)
        return await self._settle_active_usages(db=db, device=device)

    async def _settle_active_usages(self, db: AsyncSession, device: Device) -> int:
        active_usages = await device_usage_dao.get_by_device_did_status(db, device.did, UsageStatus.ACTIVE)
        if not active_usages:
            return device.quota

        now = timezone.now()
        total_consumed = 0

        for usage in active_usages:
            duration_seconds = max(int((now - usage.start_time).total_seconds()), 0)
            actual_quota = min(usage.apply_quota, duration_seconds)

            await device_usage_dao.update(
                db,
                pk=usage.id,
                obj=UpdateDeviceUsageParam(
                    actual_quota=actual_quota,
                    end_time=now,
                    status=UsageStatus.COMPLETED,
                    remark='',
                ),
            )
            total_consumed += actual_quota

        new_quota = max(device.quota - total_consumed, 0)
        await device_dao.update_model(db, device.id, {'quota': new_quota})
        device.quota = new_quota

        return new_quota

    @staticmethod
    async def _ensure_user_has_device(*, db: AsyncSession, user_id: int, device_id: int) -> Device:
        device = await device_dao.get(db, device_id)
        if not device:
            raise errors.NotFoundError(msg='设备不存在')

        result = await db.execute(
            select(user_device.c.device_id).where(
                user_device.c.user_id == user_id,
                user_device.c.device_id == device_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise errors.ForbiddenError(msg='无权操作该设备')

        return device

    @staticmethod
    async def get(*, db: AsyncSession, user_id: int, pk: int) -> Device:
        return await DeviceService._ensure_user_has_device(db=db, user_id=user_id, device_id=pk)

    @staticmethod
    async def get_by_did(*, db: AsyncSession, did: str) -> Device:
        device = await device_dao.get_by_did(db, did)
        if not device:
            raise errors.NotFoundError(msg='设备不存在')
        return device

    @staticmethod
    async def get_all(*, db: AsyncSession) -> Sequence[Device]:
        return await device_dao.get_all(db)

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        did: str | None = None,
        sn: str | None = None,
        mac: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        device_select = await device_dao.get_select(
            did=did,
            sn=sn,
            mac=mac,
            model=model,
        )
        return await paging_data(db, device_select)

    @staticmethod
    async def get_state(*, db: AsyncSession, user_id: int, pk: int) -> dict[str, Any] | None:
        device = await DeviceService._ensure_user_has_device(db=db, user_id=user_id, device_id=pk)
        return await StateStore.get(device.did)

    @staticmethod
    async def update(*, db: AsyncSession, user_id: int, pk: int, obj: UpdateDeviceParam) -> int:
        await DeviceService._ensure_user_has_device(db=db, user_id=user_id, device_id=pk)
        return await device_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, user_id: int, pk: int) -> int:
        await DeviceService._ensure_user_has_device(db=db, user_id=user_id, device_id=pk)
        await db.execute(update(Baby).where(Baby.device_id == pk).values(device_id=None))
        await db.execute(delete(user_device).where(user_device.c.device_id == pk))
        return await device_dao.delete(db, pk)


device_service: DeviceService = DeviceService()
