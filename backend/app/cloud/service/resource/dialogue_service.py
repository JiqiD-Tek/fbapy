# -*- coding: UTF-8 -*-
"""
Cloud dialogue service.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.resource.crud_dialogue import cloud_dialogue_dao
from backend.app.cloud.model import CloudDialogue
from backend.app.cloud.schema.resource.dialogue import (
    CreateDialogueParam,
    UpdateDialogueParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class CloudDialogueService:
    @staticmethod
    async def get_dialogue(*, db: AsyncSession, pk: int) -> CloudDialogue:
        dialogue = await cloud_dialogue_dao.get(db, pk)
        if not dialogue:
            raise errors.NotFoundError(msg='对话内容不存在')
        return dialogue

    @staticmethod
    async def get_dialogue_list(
        *,
        db: AsyncSession,
        title: str | None = None,
        author: str | None = None,
        status: int | None = None,
    ) -> dict[str, Any]:
        dialogue_select = await cloud_dialogue_dao.get_select(
            title=title,
            author=author,
            status=status,
        )
        return await paging_data(db, dialogue_select)

    async def create_dialogue(
        self,
        *,
        db: AsyncSession,
        obj: CreateDialogueParam,
    ) -> CloudDialogue:
        self._validate_create_payload(obj)
        return await cloud_dialogue_dao.create(db, self._normalize_create_obj(obj))

    async def update_dialogue(
        self,
        *,
        db: AsyncSession,
        pk: int,
        obj: UpdateDialogueParam,
    ) -> int:
        dialogue = await cloud_dialogue_dao.get(db, pk)
        if not dialogue:
            raise errors.NotFoundError(msg='对话内容不存在')

        payload = obj.model_dump(exclude_unset=True)
        if not payload:
            raise errors.RequestError(msg='更新内容不能为空')

        self._validate_update_payload(payload)
        return await cloud_dialogue_dao.update(
            db,
            pk,
            self._normalize_update_payload(payload),
        )

    async def delete_dialogue(self, *, db: AsyncSession, pk: int) -> int:
        dialogue = await cloud_dialogue_dao.get(db, pk)
        if not dialogue:
            raise errors.NotFoundError(msg='对话内容不存在')
        return await cloud_dialogue_dao.delete(db, pk)

    @staticmethod
    def _normalize_create_obj(obj: CreateDialogueParam) -> CreateDialogueParam:
        return obj.model_copy(update={'content': obj.content.model_dump()})

    @staticmethod
    def _normalize_update_payload(payload: dict[str, Any]) -> dict[str, Any]:
        normalized_payload = dict(payload)
        content = normalized_payload.get('content')
        if content is not None and hasattr(content, 'model_dump'):
            normalized_payload['content'] = content.model_dump()
        return normalized_payload

    @staticmethod
    def _validate_create_payload(obj: CreateDialogueParam) -> None:
        if not obj.title.strip():
            raise errors.RequestError(msg='名称不能为空')

    @staticmethod
    def _validate_update_payload(payload: dict[str, Any]) -> None:
        if 'title' in payload and payload['title'] is not None and not str(payload['title']).strip():
            raise errors.RequestError(msg='名称不能为空')
        if 'content' in payload and payload['content'] is None:
            raise errors.RequestError(msg='结构化内容不能为空')


cloud_dialogue_service: CloudDialogueService = CloudDialogueService()
