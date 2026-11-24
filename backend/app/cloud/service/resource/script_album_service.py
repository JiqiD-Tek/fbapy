# -*- coding: UTF-8 -*-
"""剧本专辑服务。"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.resource.crud_script import script_dao
from backend.app.cloud.crud.resource.crud_script_album import script_album_dao
from backend.app.cloud.model import Script, ScriptAlbum
from backend.app.cloud.schema.resource.script import ScriptResourceType
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
            status: int | None = None, resource_type: ScriptResourceType | None = None,
    ) -> dict[str, Any]:
        stmt = await script_album_dao.get_select(
            title=title, author=author, status=status, resource_type=resource_type,
        )
        return await paging_data(db, stmt)

    @staticmethod
    async def get_album_by_toy_ids(
            *, db: AsyncSession, toy_ids: list[int],
    ) -> tuple[ScriptAlbum, list[Script]] | None:
        normalized_toy_ids = ScriptAlbumService._normalize_ids(toy_ids)
        if not normalized_toy_ids:
            return None

        album = await script_album_dao.get_by_exact_toy_ids(db=db, toy_ids=normalized_toy_ids)
        if album is None:
            return None

        scripts_result = await db.execute(
            select(Script)
            .where(
                Script.deleted == 0,
                Script.album_id == album.id,
                Script.resource_type == album.resource_type,
            )
            .order_by(Script.album_id.asc(), Script.track_no.asc(), Script.id.asc())
        )
        return album, list(scripts_result.scalars().all())

    @staticmethod
    async def create_album(*, db: AsyncSession, obj: CreateScriptAlbumParam) -> ScriptAlbum:
        if not obj.title.strip():
            raise errors.RequestError(msg='剧本专辑标题不能为空')
        await ScriptAlbumService._ensure_toy_ids_available(db=db, toy_ids=obj.toy_ids)
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
            existing = await script_album_dao.get_by_exact_toy_ids(db=db, toy_ids=payload['toy_ids'])
            if existing is not None and existing.id != album.id:
                raise errors.ConflictError(msg='相同玩偶组合的剧本专辑已存在')
            expected = set(payload['toy_ids'])
            for content in await script_album_dao.get_script_contents(db, pk):
                if {line['toy_id'] for line in content} != expected:
                    raise errors.RequestError(msg='专辑下已有剧本的玩偶内容与新玩偶集合不一致')
        return await script_album_dao.update(db, pk, payload)

    @staticmethod
    async def _ensure_toy_ids_available(*, db: AsyncSession, toy_ids: list[int]) -> None:
        if await script_album_dao.get_by_exact_toy_ids(db=db, toy_ids=toy_ids) is not None:
            raise errors.ConflictError(msg='相同玩偶组合的剧本专辑已存在')

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
