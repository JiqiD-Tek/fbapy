from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.crud_user import user_dao
from backend.app.cloud.crud.device.crud_device import device_dao
from backend.app.cloud.model import Baby, Device
from backend.app.cloud.model.m2m import user_device
from backend.app.cloud.schema.user import UserDeviceParam
from backend.common.exception import errors
from backend.common.pagination import paging_data


class UserService:
    """User service"""

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        user_id: int,
        unionid: str | None = None,
        username: str | None = None,
        nickname: str | None = None,
        phone: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        user_select = await user_dao.get_select(
            user_id=user_id,
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
    async def bind_device(*, db: AsyncSession, obj: UserDeviceParam) -> None:
        if await user_dao.get(db, obj.user_id) is None:
            raise errors.NotFoundError(msg='用户不存在')
        if await device_dao.get(db, obj.device_id) is None:
            raise errors.NotFoundError(msg='设备不存在')

        result = await db.execute(select(user_device.c.user_id).where(user_device.c.device_id == obj.device_id))
        bound_user_ids = set(result.scalars().all())
        if obj.user_id in bound_user_ids:
            return
        if bound_user_ids:
            raise errors.ConflictError(msg='该设备已绑定其他用户')

        await db.execute(insert(user_device), obj.model_dump())

    @staticmethod
    async def unbind_device(*, db: AsyncSession, obj: UserDeviceParam) -> None:
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


user_service: UserService = UserService()
