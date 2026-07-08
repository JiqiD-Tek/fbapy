# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : role_service.py
@Author  : OpenAI
@Date    : 2026/07/06
"""

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.resource.crud_role import cloud_role_dao
from backend.app.cloud.model import CloudRole
from backend.app.cloud.schema.resource.role import CreateRoleParam, UpdateRoleParam
from backend.common.exception import errors
from backend.common.pagination import paging_data


class CloudRoleService:
    @staticmethod
    async def get_role(*, db: AsyncSession, pk: int) -> CloudRole:
        role = await cloud_role_dao.get(db, pk)
        if not role:
            raise errors.NotFoundError(msg='角色不存在')
        return role

    @staticmethod
    async def get_role_list(
        *,
        db: AsyncSession,
        role_key: str | None = None,
        group_key: str | None = None,
        name: str | None = None,
        voice_language: str | None = None,
        status: int | None = None,
    ) -> dict[str, Any]:
        role_select = await cloud_role_dao.get_select(
            role_key=CloudRoleService._normalize_query_text(role_key),
            group_key=CloudRoleService._normalize_query_text(group_key),
            name=CloudRoleService._normalize_query_text(name),
            voice_language=CloudRoleService._normalize_query_text(voice_language),
            status=status,
        )
        return await paging_data(db, role_select)

    @staticmethod
    async def get_enabled_role_list(
        *,
        db: AsyncSession,
        group_key: str | None = None,
        voice_language: str | None = None,
    ) -> list[CloudRole]:
        return list(
            await cloud_role_dao.get_enabled(
                db,
                group_key=CloudRoleService._normalize_query_text(group_key),
                voice_language=CloudRoleService._normalize_query_text(voice_language),
            )
        )

    @staticmethod
    async def create_role(*, db: AsyncSession, obj: CreateRoleParam) -> CloudRole:
        payload = CloudRoleService._normalize_payload(obj.model_dump())
        CloudRoleService._validate_role_key(payload)
        CloudRoleService._validate_voice_binding(payload)
        await CloudRoleService._ensure_role_key_unique(db=db, role_key=payload['role_key'])
        try:
            return await cloud_role_dao.create(db, payload)
        except IntegrityError:
            raise errors.ConflictError(msg='角色唯一标识已存在') from None

    @staticmethod
    async def update_role(*, db: AsyncSession, pk: int, obj: UpdateRoleParam) -> int:
        role = await cloud_role_dao.get(db, pk)
        if not role:
            raise errors.NotFoundError(msg='角色不存在')

        payload = CloudRoleService._normalize_payload(obj.model_dump(exclude_unset=True))
        if not payload:
            raise errors.RequestError(msg='更新内容不能为空')

        next_role_key = payload.get('role_key')
        if next_role_key is not None:
            CloudRoleService._validate_role_key(payload)
            await CloudRoleService._ensure_role_key_unique(
                db=db,
                role_key=next_role_key,
                exclude_id=pk,
            )

        CloudRoleService._validate_voice_binding(
            payload,
            current_role=role,
        )
        try:
            return await cloud_role_dao.update(db, pk, payload)
        except IntegrityError:
            raise errors.ConflictError(msg='角色唯一标识已存在') from None

    @staticmethod
    async def delete_role(*, db: AsyncSession, pk: int) -> int:
        role = await cloud_role_dao.get(db, pk)
        if not role:
            raise errors.NotFoundError(msg='角色不存在')
        return await cloud_role_dao.delete(db, pk)

    @staticmethod
    def _normalize_query_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
        normalized = payload.copy()
        text_fields = (
            'role_key',
            'group_key',
            'name',
            'system_prompt',
            'avatar_url',
            'summary',
            'voice_provider',
            'voice_id',
            'voice_name',
            'voice_language',
            'remark',
        )
        for field in text_fields:
            if field not in normalized:
                continue
            value = normalized[field]
            if value is None:
                continue
            stripped = str(value).strip()
            if field == 'role_key':
                normalized[field] = stripped
            else:
                normalized[field] = stripped or None
        return normalized

    @staticmethod
    def _validate_role_key(payload: dict[str, Any]) -> None:
        role_key = payload.get('role_key')
        if role_key is None or not str(role_key).strip():
            raise errors.RequestError(msg='角色唯一标识不能为空')

    @staticmethod
    def _validate_voice_binding(
        payload: dict[str, Any],
        *,
        current_role: CloudRole | None = None,
    ) -> None:
        voice_provider = payload.get('voice_provider')
        voice_id = payload.get('voice_id')

        if current_role is not None:
            if 'voice_provider' not in payload:
                voice_provider = current_role.voice_provider
            if 'voice_id' not in payload:
                voice_id = current_role.voice_id

        if (voice_provider is None) != (voice_id is None):
            raise errors.RequestError(msg='音色提供方和音色 ID 必须同时为空或同时有值')

    @staticmethod
    async def _ensure_role_key_unique(
        *,
        db: AsyncSession,
        role_key: str,
        exclude_id: int | None = None,
    ) -> None:
        current = await cloud_role_dao.get_by_role_key(db, role_key=role_key)
        if current is None:
            return
        if exclude_id is not None and int(current.id) == int(exclude_id):
            return
        raise errors.ConflictError(msg='角色唯一标识已存在')


cloud_role_service: CloudRoleService = CloudRoleService()
