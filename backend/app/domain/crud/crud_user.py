from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus, JoinConfig

from backend.app.domain.model.m2m import user_device
from backend.utils.serializers import select_join_serialize
from backend.utils.timezone import timezone
from backend.app.domain.model import User, Device
from backend.app.domain.schema.user import CreateUserParam, UpdateUserParam


class CRUDUser(CRUDPlus[User]):

    async def get(self, db: AsyncSession, pk: int) -> User | None:
        return await self.select_model(db, pk)

    async def get_select(self, name: str | None) -> Select:
        filters = {}

        if name is not None:
            filters['name__like'] = f'%{name}%'

        return await self.select_order('id', **filters)

    async def get_by_name(self, db: AsyncSession, name: str) -> User | None:
        return await self.select_model_by_column(db, name=name)

    async def get_all(self, db: AsyncSession) -> Sequence[User]:
        return await self.select_models(db)

    async def create(self, db: AsyncSession, obj: CreateUserParam) -> User:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateUserParam) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def update_login_time(self, db: AsyncSession, phone: str, email: str) -> int:
        """ 更新用户上次登录时间 """
        if phone:
            return await self.update_model_by_column(db, {'last_login_time': timezone.now()}, phone=phone)
        if email:
            return await self.update_model_by_column(db, {'last_login_time': timezone.now()}, email=email)
        return 0

    async def get_by_phone(self, db: AsyncSession, phone: str) -> User | None:
        """ 通过手机获取用户 """
        return await self.select_model_by_column(db, phone=phone)

    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        """ 通过邮箱获取用户 """
        return await self.select_model_by_column(db, email=email)

    async def get_join(
            self,
            db: AsyncSession,
            *,
            user_id: int | None = None,
    ) -> Any | None:
        """
        获取用户关联信息

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        filters = {}

        if user_id:
            filters['id'] = user_id

        result = await self.select_models(
            db,
            join_conditions=[
                JoinConfig(model=user_device, join_on=user_device.c.user_id == self.model.id),
                JoinConfig(model=Device, join_on=Device.id == user_device.c.device_id, fill_result=True),
            ],
            **filters,
        )

        return select_join_serialize(
            result,
            relationships=[
                'User-m2m-Device',
            ],
        )


user_dao: CRUDUser = CRUDUser(User)
