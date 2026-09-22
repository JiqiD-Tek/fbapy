from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cloud.model import Script, ScriptAlbum
from backend.app.cloud.schema.resource.script_album import CreateScriptAlbumParam, UpdateScriptAlbumParam


class CRUDScriptAlbum(CRUDPlus[ScriptAlbum]):
    async def get(self, db: AsyncSession, pk: int) -> ScriptAlbum | None:
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

    async def create(self, db: AsyncSession, obj: CreateScriptAlbumParam) -> ScriptAlbum:
        return await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateScriptAlbumParam | dict) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id=pk)

    async def get_script_contents(self, db: AsyncSession, album_id: int) -> list[list[dict]]:
        result = await db.execute(select(Script.content).where(Script.album_id == album_id, Script.deleted == 0))
        return list(result.scalars().all())

    async def update_track_count(self, db: AsyncSession, pk: int, track_count: int) -> int:
        return await self.update_model_by_column(db, {'track_count': track_count}, id=pk)


script_album_dao: CRUDScriptAlbum = CRUDScriptAlbum(ScriptAlbum)
