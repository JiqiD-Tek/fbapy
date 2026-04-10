from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.crud_user import user_dao
from backend.app.cloud.model import Device
from backend.app.cloud.model.m2m import user_device
from backend.app.cloud.schema.user import UserDeviceParam
from backend.common.exception import errors
from backend.common.pagination import paging_data


class UserService:
    """用户服务类"""

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
        """分页获取用户列表"""
        user_select = await user_dao.get_select(
            unionid=unionid,
            username=username,
            nickname=nickname,
            phone=phone,
            email=email,
        )
        return await paging_data(db, user_select)

    @staticmethod
    async def get_devices(*, db: AsyncSession, pk: int) -> Sequence[Device]:
        """获取用户所有设备"""
        user = await user_dao.get_join(db, user_id=pk)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')
        return user.devices

    @staticmethod
    async def bind_device(*, db: AsyncSession, obj: UserDeviceParam) -> None:
        """绑定设备"""
        stmt = (
            select(func.count())
            .select_from(user_device)
            .where(user_device.c.user_id == obj.user_id, user_device.c.device_id == obj.device_id)
        )
        result = await db.execute(stmt)
        count = result.scalar_one()
        if count > 0:
            return

        user_device_stmt = insert(user_device)
        await db.execute(user_device_stmt, obj.model_dump())

    @staticmethod
    async def unbind_device(*, db: AsyncSession, obj: UserDeviceParam) -> None:
        """解绑设备"""
        user_device_stmt = delete(user_device).where(
            user_device.c.user_id == obj.user_id, user_device.c.device_id == obj.device_id
        )
        await db.execute(user_device_stmt)


user_service: UserService = UserService()
