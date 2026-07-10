# -*- coding: UTF-8 -*-
"""
Cloud script service.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.resource.crud_script import cloud_script_dao
from backend.app.cloud.model import CloudScript
from backend.app.cloud.schema.resource.script import CreateScriptParam, UpdateScriptParam
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
        role_ids: list[int] | None = None,
        exact_role_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        script_select = await cloud_script_dao.get_select(
            title=title,
            author=author,
            status=status,
            role_ids=CloudScriptService._normalize_role_ids_filter(role_ids),
            exact_role_ids=CloudScriptService._normalize_role_ids_filter(exact_role_ids),
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

        if 'role_ids' in payload and not payload['role_ids']:
            raise errors.RequestError(msg='Role ID list cannot be empty')

        if 'content' in payload and payload['content'] is None:
            raise errors.RequestError(msg='Structured content cannot be empty')

        if 'role_ids' in payload or 'content' in payload:
            validated_script = CreateScriptParam.model_validate(
                {
                    'title': payload.get('title', script.title),
                    'version': payload.get('version', script.version),
                    'summary': payload.get('summary', script.summary),
                    'cover_url': payload.get('cover_url', script.cover_url),
                    'author': payload.get('author', script.author),
                    'role_ids': payload.get('role_ids', script.role_ids),
                    'content': payload.get('content', script.content),
                    'status': payload.get('status', script.status),
                    'remark': payload.get('remark', script.remark),
                }
            )
            if 'role_ids' in payload:
                payload['role_ids'] = validated_script.role_ids
            if 'content' in payload:
                payload['content'] = [line.model_dump(mode='python') for line in validated_script.content]

        return await cloud_script_dao.update(db, pk, payload)

    async def delete_script(self, *, db: AsyncSession, pk: int) -> int:
        script = await cloud_script_dao.get(db, pk)
        if not script:
            raise errors.NotFoundError(msg='Script does not exist')
        return await cloud_script_dao.delete(db, pk)

    @staticmethod
    def _normalize_role_ids_filter(role_ids: list[int] | None) -> list[int] | None:
        if not role_ids:
            return None
        return sorted(dict.fromkeys(int(role_id) for role_id in role_ids))


cloud_script_service: CloudScriptService = CloudScriptService()
