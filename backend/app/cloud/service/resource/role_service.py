# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : role_service.py
@Author  : OpenAI
@Date    : 2026/07/06
"""

from typing import Any, Sequence

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
            raise errors.NotFoundError(msg='Role does not exist')
        return role

    @staticmethod
    async def get_role_list(
            *,
            db: AsyncSession,
            group_key: str | None = None,
            name: str | None = None,
            voice_language: str | None = None,
            status: int | None = None,
    ) -> dict[str, Any]:
        role_select = await cloud_role_dao.get_select(
            group_key=CloudRoleService._normalize_query_text(group_key),
            name=CloudRoleService._normalize_query_text(name),
            voice_language=CloudRoleService._normalize_query_text(voice_language),
            status=status,
        )
        return await paging_data(db, role_select)

    @staticmethod
    async def get_roles_by_ids(
            *,
            db: AsyncSession,
            role_ids: list[int],
    ) -> Sequence[CloudRole]:
        if not role_ids:
            return []

        ordered_role_ids = list(dict.fromkeys(role_ids))
        roles = await cloud_role_dao.get_by_ids(db, ids=ordered_role_ids, enabled_only=True)
        role_map = {int(role.id): role for role in roles}
        missing_role_ids = [role_id for role_id in ordered_role_ids if role_id not in role_map]
        if missing_role_ids:
            missing_text = ', '.join(str(role_id) for role_id in missing_role_ids)
            raise errors.NotFoundError(msg=f'Role does not exist or is disabled: {missing_text}')
        return [role_map[role_id] for role_id in ordered_role_ids]

    @staticmethod
    async def create_role(*, db: AsyncSession, obj: CreateRoleParam) -> CloudRole:
        try:
            return await cloud_role_dao.create(db, obj)
        except IntegrityError:
            raise errors.ServerError(msg='Failed to create role, please try again later') from None

    @staticmethod
    async def update_role(*, db: AsyncSession, pk: int, obj: UpdateRoleParam) -> int:
        role = await cloud_role_dao.get(db, pk)
        if not role:
            raise errors.NotFoundError(msg='Role does not exist')

        payload = obj.model_dump(exclude_unset=True)
        if not payload:
            raise errors.RequestError(msg='Update payload cannot be empty')

        CloudRoleService._validate_voice_binding(
            payload,
            current_role=role,
        )
        try:
            return await cloud_role_dao.update(db, pk, payload)
        except IntegrityError:
            raise errors.ServerError(msg='Failed to update role, please try again later') from None

    @staticmethod
    async def delete_role(*, db: AsyncSession, pk: int) -> int:
        role = await cloud_role_dao.get(db, pk)
        if not role:
            raise errors.NotFoundError(msg='Role does not exist')
        return await cloud_role_dao.delete(db, pk)

    @staticmethod
    def _normalize_query_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

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
            raise errors.RequestError(msg='voice_provider and voice_id must both be empty or both have values')


cloud_role_service: CloudRoleService = CloudRoleService()
