# -*- coding: UTF-8 -*-
"""剧本专辑服务。"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.resource.crud_script import script_dao
from backend.app.cloud.crud.resource.crud_script_album import script_album_dao
from backend.app.cloud.model import Script, ScriptAlbum
from backend.app.cloud.schema.resource.script_album import CreateScriptAlbumParam, UpdateScriptAlbumParam
from backend.common.exception import errors
from backend.common.pagination import paging_data


class ScriptAlbumService:
    @staticmethod
    async def get_album(*, db: AsyncSession, pk: int) -> ScriptAlbum:
        album = await script_album_dao.get(db, pk)
        if not album:
            raise errors.NotFoundError(msg='剧本专辑不存在')
        return album

    @staticmethod
    async def get_album_list(
            *, db: AsyncSession, title: str | None = None, author: str | None = None,
            status: int | None = None,
    ) -> dict[str, Any]:
        stmt = await script_album_dao.get_select(title=title, author=author, status=status)
        return await paging_data(db, stmt)

    @staticmethod
    async def get_albums_by_toy_ids(
            *, db: AsyncSession, toy_ids: list[int],
    ) -> list[tuple[ScriptAlbum, list[Script]]]:
        normalized_toy_ids = ScriptAlbumService._normalize_ids(toy_ids)
        if not normalized_toy_ids:
            return []

        stmt = await script_album_dao.get_select(
            title=None,
            author=None,
            status=None,
            exact_toy_ids=normalized_toy_ids,
        )
        stmt = stmt.where(ScriptAlbum.deleted == 0)
        albums = list((await db.execute(stmt)).scalars().all())
        if not albums:
            return []

        album_ids = [album.id for album in albums]
        scripts_result = await db.execute(
            select(Script)
            .where(Script.deleted == 0, Script.album_id.in_(album_ids))
            .order_by(Script.album_id.asc(), Script.track_no.asc(), Script.id.asc())
        )
        scripts_by_album: dict[int, list[Script]] = {album_id: [] for album_id in album_ids}
        for script in scripts_result.scalars().all():
            if script.album_id is not None:
                scripts_by_album[int(script.album_id)].append(script)
        return [(album, scripts_by_album[int(album.id)]) for album in albums]

    @staticmethod
    async def create_album(*, db: AsyncSession, obj: CreateScriptAlbumParam) -> ScriptAlbum:
        if not obj.title.strip():
            raise errors.RequestError(msg='剧本专辑标题不能为空')
        return await script_album_dao.create(db, obj)

    @staticmethod
    async def update_album(*, db: AsyncSession, pk: int, obj: UpdateScriptAlbumParam) -> int:
        album = await ScriptAlbumService.get_album(db=db, pk=pk)
        payload = obj.model_dump(exclude_unset=True)
        if not payload:
            raise errors.RequestError(msg='更新内容不能为空')
        if 'title' in payload and (payload['title'] is None or not payload['title'].strip()):
            raise errors.RequestError(msg='剧本专辑标题不能为空')
        if 'toy_ids' in payload and payload['toy_ids'] is None:
            raise errors.RequestError(msg='专辑玩偶 ID 列表不能为空')
        if 'toy_ids' in payload and payload['toy_ids'] != album.toy_ids:
            expected = set(payload['toy_ids'])
            for content in await script_album_dao.get_script_contents(db, pk):
                if {line['toy_id'] for line in content} != expected:
                    raise errors.RequestError(msg='专辑下已有剧本的玩偶内容与新玩偶集合不一致')
        return await script_album_dao.update(db, pk, payload)

    @staticmethod
    async def delete_album(*, db: AsyncSession, pk: int) -> int:
        await ScriptAlbumService.get_album(db=db, pk=pk)
        if await script_dao.count_by_album_id(db, pk) > 0:
            raise errors.RequestError(msg='剧本专辑下存在剧本，无法删除')
        return await script_album_dao.delete(db, pk)

    @staticmethod
    def _normalize_ids(value: list[int] | None) -> list[int] | None:
        return sorted(dict.fromkeys(map(int, value))) if value else None


script_album_service: ScriptAlbumService = ScriptAlbumService()
