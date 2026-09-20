# -*- coding: UTF-8 -*-
"""
Cloud script service.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.resource.crud_script import cloud_script_dao
from backend.app.cloud.model import CloudScript
from backend.app.cloud.model.m2m import user_device
from backend.app.cloud.schema.resource.script import (
    CreateScriptParam,
    UpdateScriptFavoriteParam,
    UpdateScriptParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class CloudScriptService:
    @staticmethod
    async def get_script(*, db: AsyncSession, pk: int) -> CloudScript:
        script = await cloud_script_dao.get(db, pk)
        if not script:
            raise errors.NotFoundError(msg='Script does not exist')
        return script

    @staticmethod
    async def get_script_list(
            *,
            db: AsyncSession,
            title: str | None = None,
            author: str | None = None,
            status: int | None = None,
            device_id: int | None = None,
            favorite: int | None = None,
            content_types: list[int] | None = None,
            toy_ids: list[int] | None = None,
            exact_toy_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        script_select = await cloud_script_dao.get_select(
            title=title,
            author=author,
            status=status,
            device_id=device_id,
            favorite=favorite,
            content_types=CloudScriptService._normalize_content_types_filter(content_types),
            toy_ids=CloudScriptService._normalize_toy_ids_filter(toy_ids),
            exact_toy_ids=CloudScriptService._normalize_toy_ids_filter(exact_toy_ids),
        )
        return await paging_data(db, script_select)

    async def create_script(
            self,
            *,
            db: AsyncSession,
            obj: CreateScriptParam,
    ) -> CloudScript:
        if not obj.title.strip():
            raise errors.RequestError(msg='Title cannot be empty')
        return await cloud_script_dao.create(db, obj)

    async def update_script(
            self,
            *,
            db: AsyncSession,
            pk: int,
            obj: UpdateScriptParam,
    ) -> int:
        script = await cloud_script_dao.get(db, pk)
        if not script:
            raise errors.NotFoundError(msg='Script does not exist')

        payload = obj.model_dump(exclude_unset=True)
        if not payload:
            raise errors.RequestError(msg='Update payload cannot be empty')

        if 'title' in payload and payload['title'] is not None and not str(payload['title']).strip():
            raise errors.RequestError(msg='Title cannot be empty')

        if 'toy_ids' in payload and not payload['toy_ids']:
            raise errors.RequestError(msg='Toy ID list cannot be empty')

        if 'content' in payload and payload['content'] is None:
            raise errors.RequestError(msg='Structured content cannot be empty')

        if 'toy_ids' in payload or 'content' in payload:
            validated_script = CreateScriptParam.model_validate(
                {
                    'device_id': payload.get('device_id', script.device_id),
                    'favorite': payload.get('favorite', script.favorite),
                    'title': payload.get('title', script.title),
                    'content_types': payload.get('content_types', script.content_types),
                    'version': payload.get('version', script.version),
                    'summary': payload.get('summary', script.summary),
                    'cover_url': payload.get('cover_url', script.cover_url),
                    'author': payload.get('author', script.author),
                    'play_url': payload.get('play_url', script.play_url),
                    'toy_ids': payload.get('toy_ids', script.toy_ids),
                    'content': payload.get('content', script.content),
                    'status': payload.get('status', script.status),
                    'remark': payload.get('remark', script.remark),
                }
            )
            if 'toy_ids' in payload:
                payload['toy_ids'] = validated_script.toy_ids
            if 'content' in payload:
                payload['content'] = [line.model_dump(mode='python') for line in validated_script.content]

        return await cloud_script_dao.update(db, pk, payload)

    async def update_script_favorite(
            self,
            *,
            db: AsyncSession,
            user_id: int,
            pk: int,
            obj: UpdateScriptFavoriteParam,
    ) -> int:
        await self._ensure_user_owns_device(db=db, user_id=user_id, device_id=obj.device_id)

        script = await cloud_script_dao.get(db, pk)
        if not script:
            raise errors.NotFoundError(msg='Script does not exist')

        if int(script.device_id or 0) != obj.device_id:
            raise errors.RequestError(msg='Script does not belong to current device')

        current_favorite = int(script.favorite or 0)
        if current_favorite == obj.favorite:
            return 1

        return await cloud_script_dao.update(db, pk, {'favorite': obj.favorite}) or 1

    @staticmethod
    async def _ensure_user_owns_device(*, db: AsyncSession, user_id: int, device_id: int) -> None:
        stmt = (
            select(func.count())
            .select_from(user_device)
            .where(user_device.c.user_id == user_id, user_device.c.device_id == device_id)
        )
        result = await db.execute(stmt)
        if result.scalar_one() <= 0:
            raise errors.RequestError(msg='Device does not belong to current user')

    async def delete_script(self, *, db: AsyncSession, pk: int) -> int:
        script = await cloud_script_dao.get(db, pk)
        if not script:
            raise errors.NotFoundError(msg='Script does not exist')
        return await cloud_script_dao.delete(db, pk)

    @staticmethod
    def _normalize_toy_ids_filter(toy_ids: list[int] | None) -> list[int] | None:
        if not toy_ids:
            return None
        return sorted(dict.fromkeys(int(toy_id) for toy_id in toy_ids))

    @staticmethod
    def _normalize_content_types_filter(content_types: list[int] | None) -> list[int] | None:
        if not content_types:
            return None
        normalized = sorted(dict.fromkeys(int(content_type) for content_type in content_types))
        if any(content_type < 1 or content_type > 5 for content_type in normalized):
            raise errors.RequestError(msg='内容类型必须是 1 到 5')
        return normalized


cloud_script_service: CloudScriptService = CloudScriptService()
