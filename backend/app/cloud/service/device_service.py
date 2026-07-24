# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device_service.py
@Author  : guhua@jiqid.com
@Date    : 2025/12/09 13:50
"""

from contextlib import suppress
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_pagination.api import create_page, resolve_params

from backend.app.cloud.crud.crud_device import device_dao
from backend.app.cloud.crud.crud_device_chat import device_chat_dao
from backend.app.cloud.crud.crud_user import user_dao
from backend.app.cloud.model import Baby, Toy, Device, DeviceChat, User
from backend.app.cloud.model.m2m import device_toy, user_device
from backend.app.cloud.schema.device.device_chat import CreateDeviceChatParam, DeviceChatToyInfo, GetDeviceChatDetail
from backend.app.cloud.schema.device.device import (
    DeviceToyListItem,
    DeviceToyUnlockParam,
    UpdateDeviceParam,
    UpdateFirmwareParam,
)
from backend.app.cloud.service.baby_service import baby_service
from backend.app.cloud.schema.user import UserDeviceParam
from backend.app.cloud.timeseries.state_store import StateStore
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.database.redis import redis_client

MAX_ALLOW_QUOTA = 600
SHARED_BIND_MODELS = {'k11'}


class DeviceService:
    """Device service"""

    DEVICE_TOY_UNLOCK_CACHE_PREFIX = 'fba:device:toy:unlock'
    DEVICE_TOY_UNLOCK_CACHE_TTL_SECONDS = 600

    @staticmethod
    async def _ensure_user_has_device(*, db: AsyncSession, user_id: int, device_id: int) -> Device:
        device = await device_dao.get(db, device_id)
        if not device:
            raise errors.NotFoundError(msg='设备不存在')

        # result = await db.execute(
        #     select(user_device.c.device_id).where(
        #         user_device.c.user_id == user_id,
        #         user_device.c.device_id == device_id,
        #     )
        # )
        # if result.scalar_one_or_none() is None:
        #     raise errors.NotFoundError(msg='设备不存在')

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
        from backend.app.cloud.service.baby_service import baby_service

        await db.execute(
            update(Baby)
            .where(Baby.user_id == obj.user_id, Baby.device_id == obj.device_id)
            .values(device_id=None)
        )
        await baby_service.invalidate_device_baby_cache_by_did(device.did)
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
    async def create_chat(
            *,
            db: AsyncSession,
            did: str,
            obj: CreateDeviceChatParam,
    ) -> None:
        baby = await baby_service.get_by_device_did(db=db, did=did)
        if baby is None:
            return

        payload = obj.model_dump()
        payload['device_id'] = baby.device_id
        payload['user_id'] = baby.user_id
        payload['baby_id'] = baby.id
        await device_chat_dao.create(db, DeviceChat(**payload))

    @classmethod
    async def get_chat_list(
            cls,
            *,
            db: AsyncSession,
            device_id: int,
            user_id: int,
            baby_id: int | None = None,
    ) -> dict[str, Any]:
        await DeviceService._ensure_user_has_device(db=db, user_id=user_id, device_id=device_id)
        chat_select = await device_chat_dao.get_select(
            device_id=device_id,
            baby_id=baby_id,
        )
        page_data = await paging_data(db, chat_select)
        items = page_data.get('items') or []
        chat_items = [GetDeviceChatDetail.model_validate(item) for item in items]

        toy_ids = {chat.toy_id for chat in chat_items}
        toy_map: dict[int, DeviceChatToyInfo] = {}
        if toy_ids:
            result = await db.execute(select(Toy).where(Toy.deleted == 0, Toy.id.in_(toy_ids)))
            toy_map = {
                int(toy.id): DeviceChatToyInfo.model_validate(toy)
                for toy in result.scalars().all()
            }

        page_data['items'] = [
            chat.model_copy(update={'toy': toy_map.get(chat.toy_id)}).model_dump()
            for chat in chat_items
        ]
        return page_data

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

    @classmethod
    async def unlock_toy(
            cls,
            *,
            db: AsyncSession,
            did: str,
            obj: DeviceToyUnlockParam,
    ) -> None:
        lock_key = f'{cls.DEVICE_TOY_UNLOCK_CACHE_PREFIX}:{did}:{obj.nfc_code}'
        try:
            marked = await redis_client.set(lock_key, '1', ex=cls.DEVICE_TOY_UNLOCK_CACHE_TTL_SECONDS, nx=True)
            if not marked:
                return None

            from backend.app.cloud.service.toy_service import toy_service

            device = await DeviceService.get_by_did(db=db, did=did)
            toy_id = await toy_service.get_enabled_toy_id_by_nfc_code(db=db, nfc_code=obj.nfc_code)

            try:
                await db.execute(
                    insert(device_toy).values(
                        device_id=device.id,
                        toy_id=toy_id,
                    )
                )
            except IntegrityError:
                return None
            return None
        except Exception:
            with suppress(Exception):
                await redis_client.delete(lock_key)
            raise

    @staticmethod
    async def get_device_toy_list(
            *,
            db: AsyncSession,
            user_id: int,
            device_id: int,
    ) -> dict[str, Any]:
        await DeviceService._ensure_user_has_device(db=db, user_id=user_id, device_id=device_id)
        params = resolve_params()
        raw_params = params.to_raw_params()

        unlocked_toy_subquery = (
            select(
                device_toy.c.toy_id.label('toy_id'),
                device_toy.c.created_time.label('unlocked_at'),
            )
            .where(device_toy.c.device_id == device_id)
            .subquery()
        )

        stmt = (
            select(
                Toy.id.label('toy_id'),
                Toy.series_id,
                Toy.name,
                Toy.avatar_url,
                Toy.summary,
                unlocked_toy_subquery.c.unlocked_at,
            )
            .select_from(Toy)
            .outerjoin(unlocked_toy_subquery, unlocked_toy_subquery.c.toy_id == Toy.id)
            .where(
                Toy.deleted == 0,
                Toy.status == 1,
            )
            .order_by(
                sa.case((unlocked_toy_subquery.c.unlocked_at.is_(None), 1), else_=0).asc(),
                unlocked_toy_subquery.c.unlocked_at.desc(),
                Toy.sort.asc(),
                Toy.id.desc(),
            )
        )
        count_stmt = select(sa.func.count()).select_from(Toy).where(
            Toy.deleted == 0,
            Toy.status == 1,
        )

        if raw_params.limit is not None:
            stmt = stmt.limit(raw_params.limit)
        if raw_params.offset is not None:
            stmt = stmt.offset(raw_params.offset)

        total_result = await db.execute(count_stmt)
        total = int(total_result.scalar_one() or 0)

        result = await db.execute(stmt)
        rows = result.mappings().all()

        items: list[DeviceToyListItem] = []
        for row in rows:
            unlocked_at = row['unlocked_at']
            items.append(
                DeviceToyListItem(
                    toy_id=int(row['toy_id']),
                    series_id=row['series_id'],
                    name=row['name'],
                    avatar_url=row['avatar_url'],
                    summary=row['summary'],
                    is_unlocked=unlocked_at is not None,
                    unlocked_at=unlocked_at,
                )
            )

        return create_page(items, total=total, params=params).model_dump()

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
        device = await DeviceService._ensure_user_has_device(db=db, user_id=user_id, device_id=pk)
        old_did = device.did
        count = await device_dao.update(db, pk, obj)
        if obj.did is not None and obj.did != old_did:
            from backend.app.cloud.service.baby_service import baby_service

            await baby_service.invalidate_device_baby_cache_by_did(old_did)
            await baby_service.invalidate_device_baby_cache_by_did(obj.did)
        return count

    @staticmethod
    async def update_firmware(*, db: AsyncSession, did: str, obj: UpdateFirmwareParam) -> int:
        device = await DeviceService.get_by_did(db=db, did=did)
        return await device_dao.update_model(db, device.id, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, user_id: int, pk: int) -> Device | None:
        device = await DeviceService._ensure_user_has_device(db=db, user_id=user_id, device_id=pk)
        from backend.app.cloud.service.baby_service import baby_service

        await db.execute(update(Baby).where(Baby.device_id == pk).values(device_id=None))
        await baby_service.invalidate_device_baby_cache_by_did(device.did)
        await db.execute(delete(user_device).where(user_device.c.device_id == pk))
        await db.execute(delete(device_toy).where(device_toy.c.device_id == pk))
        count = await device_dao.delete(db, pk)
        if count <= 0:
            return None
        return device


device_service: DeviceService = DeviceService()
