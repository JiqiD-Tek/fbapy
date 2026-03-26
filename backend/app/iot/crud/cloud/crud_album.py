from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.iot.model import CloudAlbum
from backend.app.iot.schema.cloud.album import CreateAlbumParam, UpdateAlbumParam


class CRUDCloudAlbum(CRUDPlus[CloudAlbum]):
    async def get(self, db: AsyncSession, pk: int) -> CloudAlbum | None:
        return await self.select_model(db, pk)

    async def get_select(
        self,
        title: str | None,
        content_type: str | None,
        status: int | None,
    ) -> Select:
        filters = {}

        if title is not None:
            filters['title__like'] = f'%{title}%'
        if content_type is not None:
            filters['content_type'] = content_type
        if status is not None:
            filters['status'] = status

        return await self.select_order('id', **filters)

    async def get_all(self, db: AsyncSession) -> Sequence[CloudAlbum]:
        return await self.select_models(db)

    async def create(self, db: AsyncSession, obj: CreateAlbumParam) -> CloudAlbum:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateAlbumParam) -> int:
        return await self.update_model(db, pk, obj)

    async def update_track_count(self, db: AsyncSession, pk: int, track_count: int) -> int:
        return await self.update_model_by_column(db, {'track_count': track_count}, id=pk)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id=pk)


cloud_album_dao: CRUDCloudAlbum = CRUDCloudAlbum(CloudAlbum)
