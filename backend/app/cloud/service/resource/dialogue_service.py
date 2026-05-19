# -*- coding: UTF-8 -*-
"""
Cloud dialogue service.
"""

import random
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.resource.crud_dialogue import cloud_dialogue_dao
from backend.app.cloud.model import CloudDialogue
from backend.database.redis import redis_client
from backend.app.cloud.schema.resource.dialogue import (
    CreateDialogueParam,
    UpdateDialogueParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class CloudDialogueService:
    RANDOM_DIALOGUE_QUEUE_PREFIX = 'fba:dialogue:random:queue'
    RANDOM_DIALOGUE_LOCK_PREFIX = 'fba:dialogue:random:lock'

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
        if not obj.title.strip():
            raise errors.RequestError(msg='名称不能为空')
        return await cloud_dialogue_dao.create(db, obj)

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

        if 'title' in payload and payload['title'] is not None and not str(payload['title']).strip():
            raise errors.RequestError(msg='名称不能为空')

        if 'content' in payload:
            if payload['content'] is None:
                raise errors.RequestError(msg='结构化内容不能为空')
        return await cloud_dialogue_dao.update(db, pk, payload)

    async def delete_dialogue(self, *, db: AsyncSession, pk: int) -> int:
        dialogue = await cloud_dialogue_dao.get(db, pk)
        if not dialogue:
            raise errors.NotFoundError(msg='对话内容不存在')
        return await cloud_dialogue_dao.delete(db, pk)

    async def get_random_dialogue(self, *, db: AsyncSession, did: str) -> CloudDialogue:
        normalized_did = str(did or '').strip()
        if not normalized_did:
            raise errors.RequestError(msg='设备 DID 不能为空')

        queue_key = f'{self.RANDOM_DIALOGUE_QUEUE_PREFIX}:{normalized_did}'
        for force_rebuild in (False, True):
            dialogue_id = await self._pop_random_dialogue_id(
                db=db,
                did=normalized_did,
                queue_key=queue_key,
                force_rebuild=force_rebuild,
            )
            dialogue = await cloud_dialogue_dao.get(db, dialogue_id)
            if dialogue is not None and int(dialogue.status or 0) == 1:
                return dialogue

        raise errors.NotFoundError(msg='暂无可用对话资源')

    async def _pop_random_dialogue_id(
        self,
        *,
        db: AsyncSession,
        did: str,
        queue_key: str,
        force_rebuild: bool = False,
    ) -> int:
        if force_rebuild:
            await redis_client.delete(queue_key)

        dialogue_id = await redis_client.lpop(queue_key)
        if dialogue_id is None:
            await self._rebuild_random_dialogue_queue(db=db, did=did, queue_key=queue_key)
            dialogue_id = await redis_client.lpop(queue_key)

        if dialogue_id is None:
            raise errors.NotFoundError(msg='暂无可用对话资源')
        return int(dialogue_id)

    async def _rebuild_random_dialogue_queue(
        self,
        *,
        db: AsyncSession,
        did: str,
        queue_key: str,
    ) -> None:
        lock = redis_client.lock(
            f'{self.RANDOM_DIALOGUE_LOCK_PREFIX}:{did}',
            timeout=30,
            blocking_timeout=10,
        )
        await lock.acquire()
        try:
            if await redis_client.llen(queue_key):
                return

            dialogue_ids = await cloud_dialogue_dao.get_enabled_ids(db)
            if not dialogue_ids:
                return

            random.shuffle(dialogue_ids)
            pipe = redis_client.pipeline(transaction=True)
            pipe.delete(queue_key)
            pipe.rpush(queue_key, *dialogue_ids)
            await pipe.execute()
        finally:
            if await lock.owned():
                await lock.release()


cloud_dialogue_service: CloudDialogueService = CloudDialogueService()
