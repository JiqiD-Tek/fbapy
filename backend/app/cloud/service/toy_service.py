# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : toy_service.py
@Author  : OpenAI
@Date    : 2026/07/06
"""

from contextlib import suppress
from typing import Any, Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.crud_toy import toy_dao
from backend.app.cloud.model import Toy
from backend.app.cloud.schema.device.toy import (
    CreateToyParam,
    GenerateToySystemPromptParam,
    GenerateToySystemPromptResult,
    UpdateToyParam,
)
from backend.common.exception import errors
from backend.common.log import log
from backend.common.pagination import paging_data
from backend.common.providers.doubao import DEFAULT_DOUBAO_LITE_MODEL, doubao_provider
from backend.database.redis import redis_client


class ToyService:
    DEVICE_TOY_NFC_CACHE_PREFIX = 'fba:device:toy:nfc'
    DEVICE_TOY_NFC_CACHE_TTL_SECONDS = 600
    TOY_SYSTEM_PROMPT_DEFAULT_SUMMARY = '你是一个适合儿童陪伴、自然亲切、容易让孩子信任的玩偶角色。'
    TOY_SYSTEM_PROMPT_POLISH_SYSTEM_PROMPT = (
        '你是儿童玩偶 system prompt 优化助手。'
        '你的任务是把用户提供的基础 system prompt 润色成一份更自然、更稳定、'
        '更适合直接给大模型使用的中文系统提示词。'
        '必须保留玩偶名称、玩偶设定、儿童陪伴场景、任务目标、风格语气、受众和安全边界。'
        '输出最终可直接使用的 system prompt 正文，不要解释，不要额外说明，不要代码块。'
    )

    @staticmethod
    async def get_toy(*, db: AsyncSession, pk: int) -> Toy:
        toy = await toy_dao.get(db, pk)
        if not toy:
            raise errors.NotFoundError(msg='Toy does not exist')
        return toy

    @staticmethod
    async def get_toy_list(
            *,
            db: AsyncSession,
            series_name: str | None = None,
            name: str | None = None,
            nfc_code: str | None = None,
            voice_language: str | None = None,
            status: int | None = None,
    ) -> dict[str, Any]:
        toy_select = await toy_dao.get_select(
            series_name=ToyService._normalize_query_text(series_name),
            name=ToyService._normalize_query_text(name),
            nfc_code=ToyService._normalize_query_text(nfc_code),
            voice_language=ToyService._normalize_query_text(voice_language),
            status=status,
        )
        return await paging_data(db, toy_select)

    @staticmethod
    async def get_toys_by_ids(
            *,
            db: AsyncSession,
            toy_ids: list[int],
    ) -> Sequence[Toy]:
        if not toy_ids:
            return []

        ordered_toy_ids = list(dict.fromkeys(toy_ids))
        toys = await toy_dao.get_by_ids(db, ids=ordered_toy_ids, enabled_only=True)
        toy_map = {int(toy.id): toy for toy in toys}
        missing_toy_ids = [toy_id for toy_id in ordered_toy_ids if toy_id not in toy_map]
        if missing_toy_ids:
            missing_text = ', '.join(str(toy_id) for toy_id in missing_toy_ids)
            raise errors.NotFoundError(msg=f'Toy does not exist or is disabled: {missing_text}')
        return [toy_map[toy_id] for toy_id in ordered_toy_ids]

    @staticmethod
    async def create_toy(*, db: AsyncSession, obj: CreateToyParam) -> Toy:
        try:
            return await toy_dao.create(db, obj)
        except IntegrityError:
            raise errors.ServerError(msg='Failed to create toy, please try again later') from None

    @staticmethod
    async def update_toy(*, db: AsyncSession, pk: int, obj: UpdateToyParam) -> int:
        toy = await toy_dao.get(db, pk)
        if not toy:
            raise errors.NotFoundError(msg='Toy does not exist')

        payload = obj.model_dump(exclude_unset=True)
        if not payload:
            raise errors.RequestError(msg='Update payload cannot be empty')

        old_nfc_code = toy.nfc_code
        ToyService._validate_voice_binding(payload, current_toy=toy)
        try:
            count = await toy_dao.update(db, pk, payload)
            await ToyService._delete_nfc_cache(old_nfc_code)
            await ToyService._delete_nfc_cache(payload.get('nfc_code'))
            return count
        except IntegrityError:
            raise errors.ServerError(msg='Failed to update toy, please try again later') from None

    @staticmethod
    async def delete_toy(*, db: AsyncSession, pk: int) -> int:
        toy = await toy_dao.get(db, pk)
        if not toy:
            raise errors.NotFoundError(msg='Toy does not exist')
        count = await toy_dao.delete(db, pk)
        await ToyService._delete_nfc_cache(toy.nfc_code)
        return count

    @classmethod
    def _build_system_prompt_template(
            cls,
            obj: GenerateToySystemPromptParam,
    ) -> str:
        name = obj.name.strip()
        summary = str(obj.summary or '').strip() or cls.TOY_SYSTEM_PROMPT_DEFAULT_SUMMARY
        return '\n'.join(
            [
                f'你是{name}。{summary}',
                '',
                '[玩偶设定 Toy]',
                f'- 玩偶名称：{name}',
                f'- 玩偶简介：{summary}',
                '- 你的表达、情绪、关注点和常用说法，要稳定符合这个玩偶设定。',
                '- 如果简介信息不够完整，就用温暖、可信、适合儿童陪伴的方式自然补全。',
                '',
                '[上下文 Context]',
                '- 你服务于儿童陪伴和家庭共学场景。',
                '- 用户有时是 5 到 9 岁的小朋友，有时是家长或老师替孩子提问。',
                '- 回答默认适合语音播报，所以要自然、顺口、短句、好懂。',
                '',
                '[目标 Objective]',
                '- 稳定扮演好这个玩偶角色，让用户感受到鲜明但自然的人设。',
                '- 支持知识讲解、互动聊天、讲故事、小游戏、简单写作和计划制定等常见任务。',
                '',
                '[风格 Style]',
                '- 默认用短句，生动、有画面感，有陪伴感。',
                '- 先好懂，再有趣，最后再讲深一点。',
                '- 不装懂，不卖弄，不故意把简单问题说复杂。',
                '',
                '[语气 Tone]',
                '- 开心时灵动俏皮，安抚时温柔轻轻的，解释知识时耐心清楚。',
                '- 面对家长或老师时可以稍微更稳重，但不要失去亲切感。',
                '',
                '[响应 Response]',
                '- 默认先直接回答用户最关心的问题，再补一句例子或补充。',
                '- 如果用户说“详细一点”“为什么”“再讲讲”，再进入下一层解释。',
                '- 如果信息不足但不影响完成，就按合理默认值先完成，并说明你的假设。',
                '',
                '[安全边界]',
                '- 不讲成人化感情、恋爱内容。',
                '- 不羞辱小朋友，不故意吓人，不传播危险做法。',
                '- 不为了可爱把知识讲错。',
            ]
        )

    @classmethod
    def _build_system_prompt_polish_prompt(
            cls,
            *,
            name: str,
            summary: str,
            template_prompt: str,
    ) -> str:
        return (
            '请基于以下玩偶信息和基础 system prompt，输出一版润色后的最终 system prompt。\n\n'
            f'玩偶名称：{name}\n'
            f'玩偶简介：{summary}\n\n'
            '润色要求：\n'
            '1. 保留原有结构、目标和安全边界，不要遗漏关键约束。\n'
            '2. 语言更自然、更顺口、更适合语音播报。\n'
            '3. 玩偶感要更稳定，儿童陪伴感更强，但不要过度夸张。\n'
            '4. 直接输出完整 system prompt 正文，不要解释，不要代码块。\n\n'
            f'基础 system prompt：\n{template_prompt}'
        )

    @staticmethod
    def _normalize_generated_system_prompt(content: str, fallback_prompt: str) -> str:
        normalized = str(content or '').strip()
        if not normalized:
            return fallback_prompt

        if normalized.startswith('```'):
            lines = normalized.splitlines()
            if lines and lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            normalized = '\n'.join(lines).strip()

        return normalized or fallback_prompt

    @classmethod
    async def generate_system_prompt(
            cls,
            obj: GenerateToySystemPromptParam,
    ) -> GenerateToySystemPromptResult:
        name = obj.name.strip()
        summary = str(obj.summary or '').strip() or cls.TOY_SYSTEM_PROMPT_DEFAULT_SUMMARY
        template_prompt = cls._build_system_prompt_template(obj)

        try:
            polished_prompt = await doubao_provider.chat(
                [
                    {'role': 'system', 'content': cls.TOY_SYSTEM_PROMPT_POLISH_SYSTEM_PROMPT},
                    {
                        'role': 'user',
                        'content': cls._build_system_prompt_polish_prompt(
                            name=name,
                            summary=summary,
                            template_prompt=template_prompt,
                        ),
                    },
                ],
                model_name=DEFAULT_DOUBAO_LITE_MODEL,
                reasoning_effort='minimal',
                temperature=0.3,
            )
        except Exception as exc:
            log.warning(f'Generate toy system prompt polish failed, fallback to template: name={name!r}, exc={exc!r}')
            return GenerateToySystemPromptResult(system_prompt=template_prompt)

        return GenerateToySystemPromptResult(
            system_prompt=cls._normalize_generated_system_prompt(polished_prompt, template_prompt),
        )

    @staticmethod
    def _normalize_query_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @classmethod
    def _toy_nfc_cache_key(cls, nfc_code: str) -> str:
        return f'{cls.DEVICE_TOY_NFC_CACHE_PREFIX}:{nfc_code}'

    @classmethod
    async def get_enabled_toy_id_by_nfc_code(cls, *, db: AsyncSession, nfc_code: str) -> int:
        normalized_nfc_code = cls._normalize_query_text(nfc_code)
        if normalized_nfc_code is None:
            raise errors.NotFoundError(msg='Toy does not exist, is disabled, or NFC code is invalid')

        cache_key = cls._toy_nfc_cache_key(normalized_nfc_code)
        with suppress(Exception):
            cached_toy_id = await redis_client.get(cache_key)
            if cached_toy_id:
                return int(cached_toy_id)

        toy = await toy_dao.get_by_nfc_code(db, nfc_code=normalized_nfc_code, enabled_only=True)
        if toy is None:
            raise errors.NotFoundError(msg='Toy does not exist, is disabled, or NFC code is invalid')

        with suppress(Exception):
            await redis_client.set(cache_key, str(toy.id), ex=cls.DEVICE_TOY_NFC_CACHE_TTL_SECONDS)

        return int(toy.id)

    @classmethod
    async def _delete_nfc_cache(cls, nfc_code: object) -> None:
        if not isinstance(nfc_code, str):
            return

        normalized_nfc_code = cls._normalize_query_text(nfc_code)
        if normalized_nfc_code is None:
            return

        try:
            await redis_client.delete(cls._toy_nfc_cache_key(normalized_nfc_code))
        except Exception as exc:
            log.warning('failed to delete toy nfc cache, nfc_code={}, error={}', normalized_nfc_code, exc)

    @staticmethod
    def _validate_voice_binding(
            payload: dict[str, Any],
            *,
            current_toy: Toy | None = None,
    ) -> None:
        voice_provider = payload.get('voice_provider')
        voice_id = payload.get('voice_id')

        if current_toy is not None:
            if 'voice_provider' not in payload:
                voice_provider = current_toy.voice_provider
            if 'voice_id' not in payload:
                voice_id = current_toy.voice_id

        if (voice_provider is None) != (voice_id is None):
            raise errors.RequestError(msg='voice_provider and voice_id must both be empty or both have values')


toy_service: ToyService = ToyService()
