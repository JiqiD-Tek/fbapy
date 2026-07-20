# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : baby_service.py
@Author  : OpenAI
@Date    : 2026/04/17
"""

from collections.abc import Sequence
from contextlib import suppress
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.crud_baby import baby_dao
from backend.app.cloud.crud.crud_device import device_dao
from backend.app.cloud.model import Baby
from backend.app.cloud.model.m2m import user_device
from backend.app.cloud.schema.baby import CreateBabyData, CreateBabyParam, DeviceBabyParam, UpdateBabyParam
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.database.redis import redis_client


class BabyService:
    """宝宝服务类"""

    DEVICE_BABY_CACHE_PREFIX = 'fba:device:baby:did'
    DEVICE_BABY_CACHE_TTL_SECONDS = 600

    @classmethod
    def _device_baby_cache_key(cls, did: str) -> str:
        return f'{cls.DEVICE_BABY_CACHE_PREFIX}:{did}'

    @staticmethod
    async def _delete_cache_key(cache_key: str) -> None:
        with suppress(Exception):
            await redis_client.delete(cache_key)

    @classmethod
    async def invalidate_device_baby_cache_by_did(cls, did: str | None) -> None:
        if did is None:
            return

        from backend.app.cloud.timeseries.event_store import EventStore

        EventStore.invalidate_baby_id_cache(did)
        await cls._delete_cache_key(cls._device_baby_cache_key(did))

    @classmethod
    async def invalidate_device_baby_cache(cls, *, db: AsyncSession, device_id: int | None) -> None:
        if device_id is None:
            return

        device = await device_dao.get(db, device_id)
        if device is None:
            return

        await cls.invalidate_device_baby_cache_by_did(device.did)

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

    @classmethod
    async def get_by_device_did(cls, *, db: AsyncSession, did: str) -> Baby | None:
        cache_key = cls._device_baby_cache_key(did)
        cached_baby_id = None
        with suppress(Exception):
            cached_baby_id = await redis_client.get(cache_key)

        if cached_baby_id:
            try:
                baby = await baby_dao.get(db, int(cached_baby_id))
            except (TypeError, ValueError):
                await cls._delete_cache_key(cache_key)
            else:
                if baby is not None and baby.device_id is not None:
                    return baby
                await cls._delete_cache_key(cache_key)

        baby = await baby_dao.get_by_device_did(db, did=did)
        if baby is not None:
            with suppress(Exception):
                await redis_client.set(cache_key, str(baby.id), ex=cls.DEVICE_BABY_CACHE_TTL_SECONDS)
        return baby

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
        await BabyService._ensure_user_device_bound(
            db=db,
            user_id=user_id,
            device_id=obj.device_id,
            msg='请先绑定设备后再创建宝宝',
        )
        if await baby_dao.get_by_device_id(db, device_id=obj.device_id) is not None:
            raise errors.ConflictError(msg='该设备已绑定宝宝，请先解绑后再创建')

        baby_data = CreateBabyData(
            **obj.model_dump(exclude_none=True),
            user_id=user_id,
        )
        baby = await baby_dao.create(db, baby_data)
        await BabyService.invalidate_device_baby_cache(db=db, device_id=obj.device_id)
        return baby

    @staticmethod
    async def update(*, db: AsyncSession, user_id: int, pk: int, obj: UpdateBabyParam) -> int:
        await BabyService._ensure_user_has_baby(db=db, user_id=user_id, baby_id=pk)
        return await baby_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, user_id: int, pk: int) -> int:
        baby = await BabyService._ensure_user_has_baby(db=db, user_id=user_id, baby_id=pk)
        count = await baby_dao.delete(db, pk)
        if count > 0:
            await BabyService.invalidate_device_baby_cache(db=db, device_id=baby.device_id)
        return count

    @staticmethod
    async def get_user_babies(*, db: AsyncSession, user_id: int) -> Sequence[Baby]:
        return await baby_dao.get_all_by_user(db, user_id=user_id)

    @staticmethod
    async def get_device_babies(*, db: AsyncSession, user_id: int, device_id: int) -> Sequence[Baby]:
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
        await BabyService.invalidate_device_baby_cache(db=db, device_id=previous_device_id)
        await BabyService.invalidate_device_baby_cache(db=db, device_id=obj.device_id)

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
        await BabyService.invalidate_device_baby_cache(db=db, device_id=obj.device_id)


baby_service: BabyService = BabyService()
