# -*- coding: UTF-8 -*-
"""
Cloud script service.
"""

import asyncio
import json
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.resource.crud_script import cloud_script_dao
from backend.app.cloud.model import CloudScript
from backend.app.cloud.model.m2m import user_device
from backend.app.cloud.schema.resource.huoshan import HuoshanStreamTTSParam
from backend.app.cloud.schema.resource.script import (
    CreateScriptParam,
    ScriptAICreateParam,
    ScriptLine,
    UpdateScriptFavoriteParam,
    UpdateScriptParam,
)
from backend.app.cloud.service.resource.huoshan.tts.tts_cache import tts_cache
from backend.app.cloud.service.resource.huoshan.tts.tts_stream import tts_stream_service
from backend.app.cloud.service.toy_service import toy_service
from backend.common.exception import errors
from backend.common.log import log
from backend.common.pagination import paging_data
from backend.common.providers.doubao import DEFAULT_DOUBAO_MINI_MODEL, doubao_provider
from backend.database.db import async_db_session


class CloudScriptService:
    SCRIPT_AI_CREATE_SYSTEM_PROMPT = (
        '你是儿童多玩偶剧本创作助手。'
        '请根据用户提供的标题、剧本摘要和玩偶列表，创作适合儿童陪伴场景的多玩偶剧本内容。'
        '必须只使用提供的玩偶 toy_id，不要新增玩偶，不要输出玩偶列表说明。'
        '玩偶差异通过台词内容、语气和互动来体现，不要在台词里额外解释身份。'
        '只需要纯台词文本，不要加入“（轻声）”“（大声接）”“（欢快收尾）”这类括号提示。'
        '不要写“哼唱”“接唱”“合唱”“收尾”这类表演说明，也不要用引号包裹整句台词。'
        '输出必须是 JSON 数组，数组每一项只能包含 toy_id、text、audio_url 三个字段。'
        'audio_url 一律返回 null。'
        '不要输出 Markdown，不要输出代码块，不要输出 JSON 以外的任何内容。'
    )
    SCRIPT_AI_CREATE_CODE_BLOCK_RE = re.compile(r'^```(?:json)?\s*([\s\S]*?)\s*```$', re.IGNORECASE)

    def __init__(self) -> None:
        self._script_audio_tasks: dict[int, asyncio.Task[None]] = {}

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
            toy_ids: list[int] | None = None,
            exact_toy_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        script_select = await cloud_script_dao.get_select(
            title=title,
            author=author,
            status=status,
            device_id=device_id,
            favorite=favorite,
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

    async def ai_create_script_content(
            self,
            *,
            obj: ScriptAICreateParam,
    ) -> list[ScriptLine]:
        toy_ids = [toy.toy_id for toy in obj.toys]
        raw_content = await doubao_provider.chat(
            [
                {'role': 'system', 'content': self.SCRIPT_AI_CREATE_SYSTEM_PROMPT},
                {'role': 'user', 'content': self._build_ai_create_script_prompt(obj=obj)},
            ],
            model_name=DEFAULT_DOUBAO_MINI_MODEL,
            reasoning_effort='minimal',
            temperature=0.7,
        )
        return self._parse_ai_created_script_content(raw_content, toy_ids=toy_ids)

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
                    'version': payload.get('version', script.version),
                    'summary': payload.get('summary', script.summary),
                    'cover_url': payload.get('cover_url', script.cover_url),
                    'author': payload.get('author', script.author),
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
        needs_audio_generation = obj.favorite == 1 and self._has_missing_audio(script.content)
        if current_favorite == obj.favorite and not needs_audio_generation:
            return 1

        count = await cloud_script_dao.update(db, pk, {'favorite': obj.favorite})
        if needs_audio_generation:
            self._start_script_audio_generation(script_id=pk)
        return count or 1

    @staticmethod
    def _has_missing_audio(content: list[dict[str, Any]] | None) -> bool:
        for line in content or []:
            if not isinstance(line, dict):
                continue
            if not str(line.get('audio_url') or '').strip():
                return True
        return False

    def _start_script_audio_generation(self, *, script_id: int) -> None:
        current_task = self._script_audio_tasks.get(script_id)
        if current_task is not None and not current_task.done():
            return

        task = asyncio.create_task(
            self._process_script_audio_generation(script_id=script_id),
            name=f'cloud-script-audio-{script_id}',
        )
        self._script_audio_tasks[script_id] = task

        def _cleanup(done_task: asyncio.Task[None]) -> None:
            if self._script_audio_tasks.get(script_id) is done_task:
                self._script_audio_tasks.pop(script_id, None)

        task.add_done_callback(_cleanup)

    async def _process_script_audio_generation(self, *, script_id: int) -> None:
        try:
            # Let the request transaction commit before the detached session reads the row.
            await asyncio.sleep(0.1)
            async with async_db_session.begin() as db:
                script = await cloud_script_dao.get(db, script_id)
                if script is None:
                    log.warning(f'Script audio generation skipped: script_id={script_id}, reason=not_found')
                    return
                if int(script.favorite or 0) != 1:
                    log.info(f'Script audio generation skipped: script_id={script_id}, reason=not_favorite')
                    return
                if not self._has_missing_audio(script.content):
                    return

                content = await self._build_script_content_with_audio(db=db, script=script)
                await cloud_script_dao.update(db, script_id, {'content': content})
                log.info(f'Script audio generation completed: script_id={script_id}')
        except asyncio.CancelledError:
            log.warning(f'Script audio generation cancelled: script_id={script_id}')
            raise
        except Exception as exc:
            log.error(f'Script audio generation failed: script_id={script_id}, error={exc!r}')

    @staticmethod
    async def _build_script_content_with_audio(
            *,
            db: AsyncSession,
            script: CloudScript,
    ) -> list[dict[str, Any]]:
        lines = [
            ScriptLine.model_validate(line)
            for line in (script.content or [])
        ]
        missing_audio_lines = [line for line in lines if not str(line.audio_url or '').strip()]
        if not missing_audio_lines:
            return [line.model_dump(mode='python') for line in lines]

        toys = await toy_service.get_toys_by_ids(db=db, toy_ids=list(script.toy_ids or []))
        toy_map = {int(toy.id): toy for toy in toys}
        completed_lines: list[ScriptLine] = []

        for line in lines:
            if str(line.audio_url or '').strip():
                completed_lines.append(line)
                continue

            toy = toy_map.get(line.toy_id)
            speaker = str(toy.voice_id or '').strip() if toy is not None else ''
            if not speaker:
                raise errors.RequestError(
                    msg=f'Toy voice_id is required for script TTS, toy_id={line.toy_id}'
                )

            request_id = await tts_cache.create_new_request()
            await tts_stream_service.query_and_wait(
                obj=HuoshanStreamTTSParam(
                    text=line.text,
                    speaker=speaker,
                    speech_rate=0,
                    loudness_rate=0,
                ),
                request_id=request_id,
            )
            audio_url = await tts_stream_service.upload_audio_to_oss(request_id=request_id)
            completed_lines.append(line.model_copy(update={'audio_url': audio_url}, deep=True))

        return [line.model_dump(mode='python') for line in completed_lines]

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
    def _build_ai_create_script_prompt(*, obj: ScriptAICreateParam) -> str:
        toy_payload = json.dumps(
            [
                {
                    'toy_id': toy.toy_id,
                    'name': toy.name,
                    'summary': toy.summary or '',
                }
                for toy in obj.toys
            ],
            ensure_ascii=False,
        )
        summary = str(obj.summary or '').strip() or '请根据标题自由补全一个完整、自然、适合儿童收听的玩偶剧本。'
        return (
            f'剧本标题：{obj.title}\n'
            f'剧本摘要：{summary}\n'
            f'玩偶列表：{toy_payload}\n\n'
            '创作要求：\n'
            '1. 生成一个完整的小故事或情景对话，适合儿童陪伴和语音播报。\n'
            '2. 每条内容只对应一个玩偶台词。\n'
            '3. 每个提供的玩偶都必须至少出现一次。\n'
            '4. 尽量让玩偶之间有互动感，不要只是一问一答地机械重复。\n'
            '5. 玩偶差异通过说话内容、语气和互动体现，不要在台词里自我标注身份。\n'
            '6. 只输出纯台词，不要加“（轻声）”“（大声接）”“（欢快收尾）”这类括号提示，不要写哼唱、接唱、合唱等表演说明。\n'
            '7. 不要用引号包裹整句台词。\n'
            '8. 默认控制在 12 到 20 条 content 之间，句子自然、口语化、顺口。\n'
            '9. 输出必须是 JSON 数组，每项格式如下：'
            '[{"toy_id": 1, "text": "台词内容", "audio_url": null}]\n'
            '10. 不要输出标题、说明、代码块或任何 JSON 以外的内容。'
        )

    @classmethod
    def _parse_ai_created_script_content(
            cls,
            raw_content: str,
            *,
            toy_ids: list[int],
    ) -> list[ScriptLine]:
        normalized = str(raw_content or '').strip()
        if not normalized:
            raise errors.GatewayError(msg='AI script creation returned empty content')

        code_block_match = cls.SCRIPT_AI_CREATE_CODE_BLOCK_RE.match(normalized)
        if code_block_match is not None:
            normalized = code_block_match.group(1).strip()

        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError as exc:
            log.error(f'AI script creation returned invalid JSON: {normalized}')
            raise errors.GatewayError(msg='AI script creation returned invalid JSON') from exc

        if not isinstance(payload, list) or not payload:
            raise errors.GatewayError(msg='AI script creation must return a non-empty JSON array')

        content: list[ScriptLine] = []
        for item in payload:
            if not isinstance(item, dict):
                continue

            text = item.get('text')
            if not text:
                raise errors.GatewayError(msg='AI script creation returned empty line content')

            content.append(
                ScriptLine.model_validate(
                    {
                        'toy_id': item.get('toy_id'),
                        'text': text,
                        'audio_url': item.get('audio_url'),
                    }
                )
            )
        if not content:
            raise errors.GatewayError(msg='AI script creation returned empty valid content')

        allowed_toy_ids = set(toy_ids)
        invalid_toy_ids = sorted({line.toy_id for line in content if line.toy_id not in allowed_toy_ids})
        if invalid_toy_ids:
            raise errors.GatewayError(
                msg=f'AI script creation returned unexpected toy_id: {", ".join(str(toy_id) for toy_id in invalid_toy_ids)}'
            )

        missing_toy_ids = sorted(allowed_toy_ids - {line.toy_id for line in content})
        if missing_toy_ids:
            raise errors.GatewayError(
                msg=f'AI script creation did not use all toys: {", ".join(str(toy_id) for toy_id in missing_toy_ids)}'
            )

        return content


cloud_script_service: CloudScriptService = CloudScriptService()
