from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.iot.model import CloudSong
from backend.app.iot.schema.cloud.song import CreateSongParam, UpdateSongParam


class CRUDCloudSong(CRUDPlus[CloudSong]):
    async def get(self, db: AsyncSession, pk: int) -> CloudSong | None:
        return await self.select_model(db, pk)

    async def get_select(
        self,
        title: str | None,
        album_id: int | None,
        content_type: str | None,
        status: int | None,
    ) -> Select:
        filters = {}

        if title is not None:
            filters['title__like'] = f'%{title}%'
        if album_id is not None:
            filters['album_id'] = album_id
        if content_type is not None:
            filters['content_type'] = content_type
        if status is not None:
            filters['status'] = status

        return await self.select_order('id', **filters)

    async def get_all(self, db: AsyncSession) -> Sequence[CloudSong]:
        return await self.select_models(db)

    async def create(self, db: AsyncSession, obj: CreateSongParam) -> CloudSong:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateSongParam) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id=pk)

    async def count_by_album_id(self, db: AsyncSession, album_id: int) -> int:
        return await self.count(db, album_id=album_id)

    async def update_content_type_by_album_id(self, db: AsyncSession, *, album_id: int, content_type: str) -> int:
        return await self.update_model_by_column(
            db,
            {'content_type': content_type},
            allow_multiple=True,
            album_id=album_id,
        )


cloud_song_dao: CRUDCloudSong = CRUDCloudSong(CloudSong)
