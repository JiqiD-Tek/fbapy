from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.crud_user import user_dao
from backend.app.cloud.crud.crud_device import device_dao
from backend.app.cloud.model import Baby, Device
from backend.app.cloud.model.m2m import user_device
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.core.conf import settings
from backend.database.redis import redis_client


class UserService:
    """User service"""

    @staticmethod
    async def get_list(
            *,
            db: AsyncSession,
            unionid: str | None = None,
            username: str | None = None,
            nickname: str | None = None,
            phone: str | None = None,
            email: str | None = None,
    ) -> dict[str, Any]:
        user_select = await user_dao.get_select(
            unionid=unionid,
            username=username,
            nickname=nickname,
            phone=phone,
            email=email,
        )
        return await paging_data(db, user_select)

    @staticmethod
    async def get_devices(*, db: AsyncSession, user_id: int) -> Sequence[Device]:
        if await user_dao.get(db, user_id) is None:
            raise errors.NotFoundError(msg='用户不存在')

        stmt = await device_dao.get_select(user_id=user_id)
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def delete_current_user(*, db: AsyncSession, user_id: int) -> tuple[int, list[int]]:
        user = await user_dao.get(db, user_id)
        if user is None:
            raise errors.NotFoundError(msg='用户不存在')

        device_id_stmt = (
            select(Device.id)
            .join(Baby, Baby.device_id == Device.id)
            .where(Baby.user_id == user_id, Baby.device_id.is_not(None))
            .distinct()
        )
        device_id_result = await db.execute(device_id_stmt)
        device_ids = list(device_id_result.scalars().all())

        await db.execute(
            update(Baby)
            .where(Baby.user_id == user_id)
            .values(device_id=None)
        )
        await db.execute(delete(Baby).where(Baby.user_id == user_id))
        await db.execute(delete(user_device).where(user_device.c.user_id == user_id))

        count = await user_dao.delete(db, [user_id])

        await redis_client.delete_prefix(f'{settings.TOKEN_REDIS_PREFIX}:{user_id}')
        await redis_client.delete_prefix(f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:{user_id}')
        await redis_client.delete_prefix(f'{settings.TOKEN_EXTRA_INFO_REDIS_PREFIX}:{user_id}')
        await redis_client.delete_prefix(f'{settings.JWT_USER_REDIS_PREFIX}:terminal:{user_id}')

        return count, device_ids


user_service: UserService = UserService()
