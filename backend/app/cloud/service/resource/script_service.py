# -*- coding: UTF-8 -*-
"""剧本服务。"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.resource.crud_script import script_dao
from backend.app.cloud.crud.resource.crud_script_album import script_album_dao
from backend.app.cloud.model import Script
from backend.app.cloud.model.m2m import user_device
from backend.app.cloud.schema.resource.script import CreateScriptParam, UpdateScriptFavoriteParam, UpdateScriptParam
from backend.common.exception import errors
from backend.common.pagination import paging_data


class ScriptService:
    @staticmethod
    async def get_script(*, db: AsyncSession, pk: int) -> Script:
        script = await script_dao.get(db, pk)
        if not script:
            raise errors.NotFoundError(msg='剧本不存在')
        return script

    @staticmethod
    async def get_script_list(
            *, db: AsyncSession, title: str | None = None, author: str | None = None,
            status: int | None = None, device_id: int | None = None, favorite: int | None = None,
            album_id: int | None = None, content_types: list[int] | None = None,
            toy_ids: list[int] | None = None, exact_toy_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        stmt = await script_dao.get_select(
            title=title, author=author, status=status, device_id=device_id, favorite=favorite,
            album_id=album_id, content_types=ScriptService._normalize_content_types(content_types),
            toy_ids=ScriptService._normalize_ids(toy_ids), exact_toy_ids=ScriptService._normalize_ids(exact_toy_ids),
        )
        return await paging_data(db, stmt)

    @staticmethod
    async def create_script(*, db: AsyncSession, obj: CreateScriptParam) -> Script:
        if not obj.title.strip():
            raise errors.RequestError(msg='剧本标题不能为空')
        album = await script_album_dao.get(db, obj.album_id)
        if not album:
            raise errors.NotFoundError(msg='剧本专辑不存在')
        ScriptService._validate_content_toys(album.toy_ids, obj.content)
        script = await script_dao.create(db, obj)
        await ScriptService._sync_album_count(db, obj.album_id)
        return script

    @staticmethod
    async def update_script(*, db: AsyncSession, pk: int, obj: UpdateScriptParam) -> int:
        script = await ScriptService.get_script(db=db, pk=pk)
        payload = obj.model_dump(exclude_unset=True)
        if not payload:
            raise errors.RequestError(msg='更新内容不能为空')
        if 'title' in payload and (payload['title'] is None or not payload['title'].strip()):
            raise errors.RequestError(msg='剧本标题不能为空')
        target_album_id = payload.get('album_id', script.album_id)
        album = await script_album_dao.get(db, target_album_id)
        if not album:
            raise errors.NotFoundError(msg='剧本专辑不存在')
        content = payload.get('content', script.content)
        ScriptService._validate_content_toys(album.toy_ids, content)
        if 'content' in payload:
            payload['content'] = [line.model_dump(mode='python') for line in obj.content or []]
        old_album_id = script.album_id
        count = await script_dao.update(db, pk, payload)
        if target_album_id != old_album_id:
            await ScriptService._sync_album_count(db, old_album_id)
            await ScriptService._sync_album_count(db, target_album_id)
        return count

    @staticmethod
    async def update_script_favorite(
            *, db: AsyncSession, user_id: int, pk: int, obj: UpdateScriptFavoriteParam,
    ) -> int:
        result = await db.execute(
            select(func.count()).select_from(user_device).where(
                user_device.c.user_id == user_id,
                user_device.c.device_id == obj.device_id,
            )
        )
        if result.scalar_one() <= 0:
            raise errors.RequestError(msg='设备不属于当前用户')
        script = await ScriptService.get_script(db=db, pk=pk)
        if int(script.device_id or 0) != obj.device_id:
            raise errors.RequestError(msg='剧本不属于当前设备')
        return await script_dao.update(db, pk, {'favorite': obj.favorite}) or 1

    @staticmethod
    async def delete_script(*, db: AsyncSession, pk: int) -> int:
        script = await ScriptService.get_script(db=db, pk=pk)
        count = await script_dao.delete(db, pk)
        await ScriptService._sync_album_count(db, script.album_id)
        return count

    @staticmethod
    def _validate_content_toys(toy_ids: list[int], content: list[Any]) -> None:
        expected = set(toy_ids)
        actual = {line.toy_id if hasattr(line, 'toy_id') else line['toy_id'] for line in content}
        if actual != expected:
            raise errors.RequestError(msg='剧本内容中的玩偶必须与专辑玩偶集合完全一致')

    @staticmethod
    async def _sync_album_count(db: AsyncSession, album_id: int) -> None:
        count = await script_dao.count_by_album_id(db, album_id)
        await script_album_dao.update_track_count(db, album_id, count)

    @staticmethod
    def _normalize_ids(value: list[int] | None) -> list[int] | None:
        return sorted(dict.fromkeys(map(int, value))) if value else None

    @staticmethod
    def _normalize_content_types(value: list[int] | None) -> list[int] | None:
        normalized = ScriptService._normalize_ids(value)
        if normalized and any(item < 1 or item > 5 for item in normalized):
            raise errors.RequestError(msg='内容类型必须是 1 到 5')
        return normalized


script_service: ScriptService = ScriptService()
