# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : baby_service.py
@Author  : OpenAI
@Date    : 2026/04/17
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.crud_baby import baby_dao
from backend.app.cloud.crud.device.crud_device import device_dao
from backend.app.cloud.model import Baby
from backend.app.cloud.model.m2m import user_device
from backend.app.cloud.schema.baby import CreateBabyData, CreateBabyParam, DeviceBabyParam, UpdateBabyParam
from backend.common.exception import errors
from backend.common.pagination import paging_data


class BabyService:
    """宝宝服务类"""

    @staticmethod
    async def _invalidate_timeseries_baby_cache(*, db: AsyncSession, device_id: int | None) -> None:
        if device_id is None:
            return

        device = await device_dao.get(db, device_id)
        if device is None:
            return

        from backend.app.cloud.timeseries.event_store import EventStore

        EventStore.invalidate_baby_id_cache(device.did)

    @staticmethod
    async def _ensure_device_exists(*, db: AsyncSession, device_id: int) -> None:
        if await device_dao.get(db, device_id) is None:
            raise errors.NotFoundError(msg='设备不存在')

    @staticmethod
    async def _ensure_user_device_bound(*, db: AsyncSession, user_id: int, device_id: int, msg: str) -> None:
        stmt = (
            select(func.count())
            .select_from(user_device)
            .where(user_device.c.user_id == user_id, user_device.c.device_id == device_id)
        )
        result = await db.execute(stmt)
        if result.scalar_one() <= 0:
            raise errors.RequestError(msg=msg)

    @staticmethod
    async def _ensure_user_has_baby(*, db: AsyncSession, user_id: int, baby_id: int) -> Baby:
        baby = await baby_dao.get(db, baby_id)
        if baby is None:
            raise errors.NotFoundError(msg='宝宝不存在')

        if baby.user_id != user_id:
            raise errors.NotFoundError(msg='宝宝不存在')

        return baby

    @staticmethod
    async def _ensure_user_can_operate_device_baby(
            *,
            db: AsyncSession,
            user_id: int,
            device_id: int,
            baby_id: int,
    ) -> Baby:
        await BabyService._ensure_device_exists(db=db, device_id=device_id)
        await BabyService._ensure_user_device_bound(
            db=db,
            user_id=user_id,
            device_id=device_id,
            msg='当前用户未绑定该设备',
        )
        return await BabyService._ensure_user_has_baby(db=db, user_id=user_id, baby_id=baby_id)

    @staticmethod
    async def get(*, db: AsyncSession, user_id: int, pk: int) -> Baby:
        return await BabyService._ensure_user_has_baby(db=db, user_id=user_id, baby_id=pk)

    @staticmethod
    async def get_by_device_did(*, db: AsyncSession, did: str) -> Baby | None:
        return await baby_dao.get_by_device_did(db, did=did)

    @staticmethod
    async def get_list(
            *,
            db: AsyncSession,
            user_id: int,
            name: str | None = None,
            nickname: str | None = None,
            sex: int | None = None,
            device_id: int | None = None,
    ) -> dict[str, Any]:
        if device_id is not None:
            await BabyService._ensure_device_exists(db=db, device_id=device_id)
            await BabyService._ensure_user_device_bound(
                db=db,
                user_id=user_id,
                device_id=device_id,
                msg='当前用户未绑定该设备',
            )

        baby_select = await baby_dao.get_select(
            user_id=user_id,
            name=name,
            nickname=nickname,
            sex=sex,
            device_id=device_id,
        )
        return await paging_data(db, baby_select)

    @staticmethod
    async def create(*, db: AsyncSession, user_id: int, obj: CreateBabyParam) -> Baby:
        await BabyService._ensure_device_exists(db=db, device_id=obj.device_id)
        await BabyService._ensure_user_device_bound(
            db=db,
            user_id=user_id,
            device_id=obj.device_id,
            msg='请先绑定设备后再创建宝宝',
        )

        baby_data = CreateBabyData(
            **obj.model_dump(exclude_none=True),
            user_id=user_id,
        )
        baby = await baby_dao.create(db, baby_data)
        await BabyService._invalidate_timeseries_baby_cache(db=db, device_id=obj.device_id)
        return baby

    @staticmethod
    async def update(*, db: AsyncSession, user_id: int, pk: int, obj: UpdateBabyParam) -> int:
        await BabyService._ensure_user_has_baby(db=db, user_id=user_id, baby_id=pk)
        return await baby_dao.update(db, pk, obj)

    @staticmethod
    async def get_user_babies(*, db: AsyncSession, user_id: int) -> Sequence[Baby]:
        return await baby_dao.get_all_by_user(db, user_id=user_id)

    @staticmethod
    async def get_device_babies(*, db: AsyncSession, user_id: int, device_id: int) -> Sequence[Baby]:
        await BabyService._ensure_device_exists(db=db, device_id=device_id)
        await BabyService._ensure_user_device_bound(
            db=db,
            user_id=user_id,
            device_id=device_id,
            msg='当前用户未绑定该设备',
        )
        return await baby_dao.get_all_by_device(db, user_id=user_id, device_id=device_id)

    @staticmethod
    async def bind_device_baby(*, db: AsyncSession, user_id: int, obj: DeviceBabyParam) -> None:
        baby = await BabyService._ensure_user_can_operate_device_baby(
            db=db,
            user_id=user_id,
            device_id=obj.device_id,
            baby_id=obj.baby_id,
        )
        if baby.device_id == obj.device_id:
            return

        previous_device_id = baby.device_id
        await db.execute(
            update(Baby)
            .where(Baby.user_id == user_id, Baby.device_id == obj.device_id, Baby.id != obj.baby_id)
            .values(device_id=None)
        )
        await baby_dao.update_model(db, obj.baby_id, {'device_id': obj.device_id})
        await BabyService._invalidate_timeseries_baby_cache(db=db, device_id=previous_device_id)
        await BabyService._invalidate_timeseries_baby_cache(db=db, device_id=obj.device_id)

    @staticmethod
    async def unbind_device_baby(*, db: AsyncSession, user_id: int, obj: DeviceBabyParam) -> None:
        baby = await BabyService._ensure_user_can_operate_device_baby(
            db=db,
            user_id=user_id,
            device_id=obj.device_id,
            baby_id=obj.baby_id,
        )
        if baby.device_id != obj.device_id:
            raise errors.RequestError(msg='宝宝未绑定该设备')
        await baby_dao.update_model(db, obj.baby_id, {'device_id': None})
        await BabyService._invalidate_timeseries_baby_cache(db=db, device_id=obj.device_id)


baby_service: BabyService = BabyService()
