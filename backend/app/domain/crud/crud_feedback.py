from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.domain.model import Feedback
from backend.app.domain.schema.feedback import CreateFeedbackParam, UpdateFeedbackParam


class CRUDFeedback(CRUDPlus[Feedback]):

    async def get(self, db: AsyncSession, pk: int) -> Feedback | None:
        return await self.select_model(db, pk)

    async def get_select(self, name: str | None, device_id: int | None, user_id: int | None,
                         status: int | None) -> Select:
        filters = {}

        if name is not None:
            filters['name__like'] = f'%{name}%'
        if device_id is not None:
            filters['device_id'] = device_id
        if user_id is not None:
            filters['user_id'] = user_id
        if status is not None:
            filters['status'] = status

        return await self.select_order('id', **filters)

    async def get_by_name(self, db: AsyncSession, name: str) -> Feedback | None:
        return await self.select_model_by_column(db, name=name)

    async def get_all(self, db: AsyncSession) -> Sequence[Feedback]:
        return await self.select_models(db)

    async def create(self, db: AsyncSession, obj: CreateFeedbackParam) -> Feedback:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateFeedbackParam) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)


feedback_dao: CRUDFeedback = CRUDFeedback(Feedback)
