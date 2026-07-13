# -*- coding: UTF-8 -*-
"""
Cloud script service.
"""

import json
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.resource.crud_script import cloud_script_dao
from backend.app.cloud.model import CloudScript
from backend.app.cloud.schema.resource.script import (
    CreateScriptParam,
    ScriptAICreateParam,
    ScriptLine,
    UpdateScriptParam,
)
from backend.common.exception import errors
from backend.common.log import log
from backend.common.pagination import paging_data
from backend.common.providers.doubao import DEFAULT_DOUBAO_CHAT_MODEL, doubao_provider


class CloudScriptService:
    SCRIPT_AI_CREATE_SYSTEM_PROMPT = (
        '你是儿童多角色剧本创作助手。'
        '请根据用户提供的标题、剧本摘要和角色列表，创作适合儿童陪伴场景的多角色剧本内容。'
        '必须只使用提供的角色 role_id，不要新增角色，不要输出角色列表说明。'
        '角色差异通过台词内容、语气和互动来体现，不要在台词里额外解释身份。'
        '只输出纯台词，不要写哼唱、接唱、合唱等表演说明。'
        '输出必须是 JSON 数组，数组每一项只能包含 role_id、text、audio_url 三个字段。'
        'audio_url 一律返回 null。'
        '不要输出 Markdown，不要输出代码块，不要输出 JSON 以外的任何内容。'
    )
    SCRIPT_AI_CREATE_CODE_BLOCK_RE = re.compile(r'^```(?:json)?\s*([\s\S]*?)\s*```$', re.IGNORECASE)

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

    async def ai_create_script_content(
            self,
            *,
            obj: ScriptAICreateParam,
    ) -> list[ScriptLine]:
        role_ids = [role.role_id for role in obj.roles]
        raw_content = await doubao_provider.chat(
            [
                {'role': 'system', 'content': self.SCRIPT_AI_CREATE_SYSTEM_PROMPT},
                {'role': 'user', 'content': self._build_ai_create_script_prompt(obj=obj)},
            ],
            model_name=DEFAULT_DOUBAO_CHAT_MODEL,
            reasoning_effort='minimal',
            temperature=0.7,
        )
        content = self._parse_ai_created_script_content(raw_content, role_ids=role_ids)
        return content

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

    @staticmethod
    def _build_ai_create_script_prompt(*, obj: ScriptAICreateParam) -> str:
        role_payload = json.dumps(
            [
                {
                    'role_id': role.role_id,
                    'name': role.name,
                    'summary': role.summary or '',
                }
                for role in obj.roles
            ],
            ensure_ascii=False,
        )
        summary = str(obj.summary or '').strip() or '请根据标题自由补全一个完整、自然、适合儿童收听的角色剧本。'
        return (
            f'标题：{obj.title}\n'
            f'剧本摘要：{summary}\n'
            f'角色列表：{role_payload}\n\n'
            '创作要求：\n'
            '1. 生成一个完整的小故事或情景对话，适合儿童陪伴和语音播报。\n'
            '2. 每条内容只对应一个角色台词。\n'
            '3. 每个提供的角色都必须至少出现一次。\n'
            '4. 尽量让角色之间有互动感，不要只是一问一答地机械重复。\n'
            '5. 角色差异通过说话内容、语气和互动体现，不要在台词里自我标注身份。\n'
            '6. 只输出纯台词，不要写哼唱、接唱、合唱等表演说明。\n'
            '7. 不要用引号包裹整句台词。\n'
            '8. 默认控制在 12 到 20 条 content 之间，句子自然、口语化、顺口。\n'
            '9. 输出必须是 JSON 数组，每项格式如下：'
            '[{"role_id": 1, "text": "台词内容", "audio_url": null}]\n'
            '10. 不要输出标题、说明、代码块或任何 JSON 以外的内容。'
        )

    @classmethod
    def _parse_ai_created_script_content(
            cls,
            raw_content: str,
            *,
            role_ids: list[int],
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
                        'role_id': item.get('role_id'),
                        'text': text,
                        'audio_url': item.get('audio_url'),
                    }
                )
            )
        if not content:
            raise errors.GatewayError(msg='AI script creation returned empty valid content')

        allowed_role_ids = set(role_ids)
        invalid_role_ids = sorted({line.role_id for line in content if line.role_id not in allowed_role_ids})
        if invalid_role_ids:
            raise errors.GatewayError(
                msg=f'AI script creation returned unexpected role_id: {", ".join(str(role_id) for role_id in invalid_role_ids)}'
            )

        missing_role_ids = sorted(allowed_role_ids - {line.role_id for line in content})
        if missing_role_ids:
            raise errors.GatewayError(
                msg=f'AI script creation did not use all roles: {", ".join(str(role_id) for role_id in missing_role_ids)}'
            )

        return content


cloud_script_service: CloudScriptService = CloudScriptService()
