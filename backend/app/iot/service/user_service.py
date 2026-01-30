from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, insert, select, func

from backend.app.iot.crud.crud_user import user_dao
from backend.app.iot.model import Device
from backend.app.iot.model.m2m import user_device
from backend.app.iot.schema.user import UserDeviceParam

from backend.common.exception import errors


class UserService:
    """用户服务类"""

    @staticmethod
    async def get_devices(*, db: AsyncSession, pk: int) -> Sequence[Device]:
        """ 获取用户所有设备 """
        user = await user_dao.get_join(db, user_id=pk)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')
        return user.devices

    @staticmethod
    async def bind_device(*, db: AsyncSession, obj: UserDeviceParam) -> None:
        """ 绑定设备 """
        stmt = select(func.count()).select_from(user_device).where(
            user_device.c.user_id == obj.user_id, user_device.c.device_id == obj.device_id)
        result = await db.execute(stmt)
        count = result.scalar_one()
        if count > 0:
            return

        user_device_stmt = insert(user_device)
        await db.execute(user_device_stmt, obj.model_dump())

    @staticmethod
    async def unbind_device(*, db: AsyncSession, obj: UserDeviceParam) -> None:
        """ 解绑设备 """
        user_device_stmt = delete(user_device).where(
            user_device.c.user_id == obj.user_id, user_device.c.device_id == obj.device_id)
        await db.execute(user_device_stmt)


user_service: UserService = UserService()
