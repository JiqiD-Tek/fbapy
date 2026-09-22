from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import SongAlbum
from backend.app.cloud.schema.resource.song_album import CreateSongAlbumParam, UpdateSongAlbumParam


class CRUDSongAlbum(CRUDPlus[SongAlbum]):
    async def get(self, db: AsyncSession, pk: int) -> SongAlbum | None:
        return await self.select_model(db, pk)

    async def get_select(
            self,
            title: str | None,
            content_type: int | None,
            status: int | None,
            column: str = 'id',
            order: str = 'desc',
    ) -> Select:
        filters = {}
        if title is not None:
            filters['title__like'] = f'%{title}%'
        if content_type is not None:
            filters['content_type'] = content_type
        if status is not None:
            filters['status'] = status
        # 管理列表统一按主键倒序，保证最新创建的数据优先展示。
        return await self.select_order('id', 'desc', **filters)

    async def get_all(self, db: AsyncSession) -> Sequence[SongAlbum]:
        return await self.select_models(db)

    async def create(self, db: AsyncSession, obj: CreateSongAlbumParam) -> SongAlbum:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateSongAlbumParam) -> int:
        return await self.update_model(db, pk, obj)

    async def update_track_count(self, db: AsyncSession, pk: int, track_count: int) -> int:
        return await self.update_model_by_column(db, {'track_count': track_count}, id=pk)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id=pk)


song_album_dao: CRUDSongAlbum = CRUDSongAlbum(SongAlbum)
