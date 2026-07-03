# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device_service.py
@Author  : guhua@jiqid.com
@Date    : 2025/12/09 13:50
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.crud_user import user_dao
from backend.app.cloud.crud.crud_device import device_dao
from backend.app.cloud.model import Baby, Device, User
from backend.app.cloud.model.m2m import user_device
from backend.app.cloud.schema.device.device import UpdateDeviceParam, UpdateFirmwareParam
from backend.app.cloud.schema.user import UserDeviceParam
from backend.app.cloud.timeseries.state_store import StateStore
from backend.common.exception import errors
from backend.common.pagination import paging_data

MAX_ALLOW_QUOTA = 600
SHARED_BIND_MODELS = {'k11'}


class DeviceService:
    """Device service"""

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
    async def bind_device(
            *,
            db: AsyncSession,
            obj: UserDeviceParam,
    ) -> None:
        if await user_dao.get(db, obj.user_id) is None:
            raise errors.NotFoundError(msg='用户不存在')
        if (device := await device_dao.get(db, obj.device_id)) is None:
            raise errors.NotFoundError(msg='设备不存在')

        result = await db.execute(select(user_device.c.user_id).where(user_device.c.device_id == obj.device_id))
        bound_user_ids = set(result.scalars().all())
        if obj.user_id in bound_user_ids:
            return None

        allow_shared = (device.model or '').lower() in SHARED_BIND_MODELS
        if bound_user_ids and not allow_shared:
            raise errors.ConflictError(msg='该设备已绑定其他用户')

        await db.execute(insert(user_device), obj.model_dump())
        return None

    @staticmethod
    async def unbind_device(*, db: AsyncSession, obj: UserDeviceParam) -> Device:
        device = await DeviceService._ensure_user_has_device(db=db, user_id=obj.user_id, device_id=obj.device_id)
        await db.execute(
            update(Baby)
            .where(Baby.user_id == obj.user_id, Baby.device_id == obj.device_id)
            .values(device_id=None)
        )
        await db.execute(
            delete(user_device).where(
                user_device.c.user_id == obj.user_id,
                user_device.c.device_id == obj.device_id,
            )
        )
        return device

    @staticmethod
    async def get_by_did(*, db: AsyncSession, did: str) -> Device:
        device = await device_dao.get_by_did(db, did)
        if not device:
            raise errors.NotFoundError(msg='设备不存在')
        return device

    @staticmethod
    async def get_bind_state(*, db: AsyncSession, did: str) -> dict[str, Any]:
        device = await DeviceService.get_by_did(db=db, did=did)

        user_stmt = (
            select(User)
            .join(user_device, user_device.c.user_id == User.id)
            .where(user_device.c.device_id == device.id)
            .limit(1)
        )
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        return {
            'is_bound': user is not None,
            'user': user,
        }

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
    async def update_firmware(*, db: AsyncSession, did: str, obj: UpdateFirmwareParam) -> int:
        device = await DeviceService.get_by_did(db=db, did=did)
        return await device_dao.update_model(db, device.id, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, user_id: int, pk: int) -> Device | None:
        device = await DeviceService._ensure_user_has_device(db=db, user_id=user_id, device_id=pk)
        await db.execute(update(Baby).where(Baby.device_id == pk).values(device_id=None))
        await db.execute(delete(user_device).where(user_device.c.device_id == pk))
        count = await device_dao.delete(db, pk)
        if count <= 0:
            return None
        return device


device_service: DeviceService = DeviceService()
