from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.domain.model import User
from backend.app.domain.schema.user import CreateUserParam, UpdateUserParam
from backend.utils.timezone import timezone


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

    async def update_login_time(self, db: AsyncSession, phone: str) -> int:
        """ 更新用户上次登录时间 """
        return await self.update_model_by_column(db, {'last_login_time': timezone.now()}, phone=phone)

    async def get_by_phone(self, db: AsyncSession, phone: str) -> User | None:
        """ 通过手机获取用户 """
        return await self.select_model_by_column(db, phone=phone)


user_dao: CRUDUser = CRUDUser(User)
