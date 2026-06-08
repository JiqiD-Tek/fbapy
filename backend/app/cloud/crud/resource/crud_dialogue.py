import sqlalchemy as sa
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import CloudDialogue
from backend.app.cloud.schema.resource.dialogue import (
    CreateDialogueParam,
    UpdateDialogueParam,
)


class CRUDCloudDialogue(CRUDPlus[CloudDialogue]):
    async def get(self, db: AsyncSession, pk: int) -> CloudDialogue | None:
        return await self.select_model(db, pk)

    async def get_select(
            self,
            title: str | None,
            author: str | None,
            status: int | None,
    ) -> Select:
        filters = {}

        if title is not None:
            filters['title__like'] = f'%{title}%'
        if author is not None:
            filters['author__like'] = f'%{author}%'
        if status is not None:
            filters['status'] = status

        return await self.select_order('id', 'desc', **filters)

    async def get_enabled_ids(self, db: AsyncSession) -> list[int]:
        stmt = sa.select(self.model.id).where(self.model.status == 1).order_by(self.model.id.asc())
        result = await db.execute(stmt)
        return [int(pk) for pk in result.scalars().all()]

    async def create(self, db: AsyncSession, obj: CreateDialogueParam) -> CloudDialogue:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateDialogueParam | dict) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id=pk)


cloud_dialogue_dao: CRUDCloudDialogue = CRUDCloudDialogue(CloudDialogue)
