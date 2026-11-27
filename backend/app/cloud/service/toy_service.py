# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : toy_service.py
@Author  : OpenAI
@Date    : 2026/07/06
"""

from typing import Any, Sequence

import sqlalchemy as sa

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.crud_toy import toy_dao, toy_series_dao
from backend.app.cloud.model import Toy, ToySeries
from backend.app.cloud.schema.device.toy import (
    CreateToyParam,
    CreateToySeriesParam,
    GenerateToySystemPromptParam,
    GenerateToySystemPromptResult,
    UpdateToyParam,
    UpdateToySeriesParam,
)
from backend.common.exception import errors
from backend.common.log import log
from backend.common.pagination import paging_data
from backend.common.providers.doubao import DEFAULT_DOUBAO_LITE_MODEL, doubao_provider


class ToyService:
    TOY_SYSTEM_PROMPT_DEFAULT_SUMMARY = '你是一个适合儿童陪伴、自然亲切、容易让孩子信任的玩偶角色。'
    TOY_SYSTEM_PROMPT_POLISH_SYSTEM_PROMPT = (
        '你是儿童玩偶系统提示词优化助手。'
        '你的任务是把用户提供的基础系统提示词润色成一份更自然、更稳定、'
        '更适合直接给大模型使用的中文系统提示词。'
        '必须保留玩偶名称、玩偶设定、儿童陪伴场景、任务目标、风格语气、受众和安全边界。'
        '输出最终可直接使用的系统提示词正文，不要解释，不要额外说明，不要代码块。'
    )

    @staticmethod
    async def get_toy_series(*, db: AsyncSession, pk: int) -> ToySeries:
        series = await toy_series_dao.get(db, pk)
        if not series:
            raise errors.NotFoundError(msg='玩偶系列不存在')
        return series

    @staticmethod
    async def get_toy_series_list(
            *,
            db: AsyncSession,
            name: str | None = None,
            status: int | None = None,
    ) -> dict[str, Any]:
        series_select = await toy_series_dao.get_select(
            name=ToyService._normalize_query_text(name),
            status=status,
        )
        return await paging_data(db, series_select)

    @staticmethod
    async def create_toy_series(*, db: AsyncSession, obj: CreateToySeriesParam) -> ToySeries:
        try:
            return await toy_series_dao.create(db, obj)
        except IntegrityError:
            raise errors.ServerError(msg='创建玩偶系列失败，请稍后重试') from None

    @staticmethod
    async def update_toy_series(*, db: AsyncSession, pk: int, obj: UpdateToySeriesParam) -> int:
        series = await toy_series_dao.get(db, pk)
        if not series:
            raise errors.NotFoundError(msg='玩偶系列不存在')

        payload = obj.model_dump(exclude_unset=True)
        if not payload:
            raise errors.RequestError(msg='更新内容不能为空')

        try:
            return await toy_series_dao.update(db, pk, payload)
        except IntegrityError:
            raise errors.ServerError(msg='更新玩偶系列失败，请稍后重试') from None

    @staticmethod
    async def delete_toy_series(*, db: AsyncSession, pk: int) -> int:
        series = await toy_series_dao.get(db, pk)
        if not series:
            raise errors.NotFoundError(msg='玩偶系列不存在')

        toy_result = await db.execute(
            sa.select(Toy.id).where(Toy.deleted == 0, Toy.series_id == pk).limit(1)
        )
        if toy_result.scalar_one_or_none() is not None:
            raise errors.ConflictError(msg='玩偶系列正在使用中，无法删除')

        return await toy_series_dao.delete(db, pk)

    @staticmethod
    async def _ensure_series_exists(*, db: AsyncSession, series_id: int | None) -> None:
        if series_id is None:
            return

        series = await toy_series_dao.get(db, series_id)
        if not series:
            raise errors.NotFoundError(msg='玩偶系列不存在')

    @staticmethod
    async def _ensure_related_toys_exist(
            *,
            db: AsyncSession,
            toy_ids: list[int] | None,
            current_toy_id: int | None = None,
    ) -> None:
        if not toy_ids:
            return

        ordered_toy_ids = list(dict.fromkeys(toy_ids))
        if current_toy_id is not None and current_toy_id in ordered_toy_ids:
            raise errors.RequestError(msg='关联玩偶不能包含当前玩偶')

        toys = await toy_dao.get_by_ids(db, ids=ordered_toy_ids, enabled_only=False)
        toy_map = {int(toy.id): toy for toy in toys}
        missing_toy_ids = [toy_id for toy_id in ordered_toy_ids if toy_id not in toy_map]
        if missing_toy_ids:
            missing_text = ', '.join(str(toy_id) for toy_id in missing_toy_ids)
            raise errors.NotFoundError(msg=f'关联玩偶不存在：{missing_text}')

    @staticmethod
    async def get_toy(*, db: AsyncSession, pk: int) -> Toy:
        toy = await toy_dao.get(db, pk)
        if not toy:
            raise errors.NotFoundError(msg='玩偶不存在')
        return toy

    @staticmethod
    async def get_related_toys(*, db: AsyncSession, toy: Toy) -> list[Toy]:
        """按玩偶保存的关联 ID 顺序获取关联玩偶，不递归加载更深层关系。"""
        related_ids = [int(toy_id) for toy_id in (toy.related_toy_ids or [])]
        if not related_ids:
            return []

        related_toys = await toy_dao.get_by_ids(db, ids=related_ids, enabled_only=False)
        toy_map = {int(item.id): item for item in related_toys}
        return [toy_map[toy_id] for toy_id in dict.fromkeys(related_ids) if toy_id in toy_map]

    @staticmethod
    async def get_toy_list(
            *,
            db: AsyncSession,
            series_id: int | None = None,
            name: str | None = None,
            tag_id: str | None = None,
            voice_language: str | None = None,
            status: int | None = None,
    ) -> dict[str, Any]:
        toy_select = await toy_dao.get_select(
            series_id=series_id,
            name=ToyService._normalize_query_text(name),
            tag_id=ToyService._normalize_query_text(tag_id),
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
            raise errors.NotFoundError(msg=f'玩偶不存在或已禁用：{missing_text}')
        return [toy_map[toy_id] for toy_id in ordered_toy_ids]

    @staticmethod
    async def create_toy(*, db: AsyncSession, obj: CreateToyParam) -> Toy:
        await ToyService._ensure_series_exists(db=db, series_id=obj.series_id)
        await ToyService._ensure_related_toys_exist(db=db, toy_ids=obj.related_toy_ids)
        try:
            return await toy_dao.create(db, obj)
        except IntegrityError:
            raise errors.ServerError(msg='创建玩偶失败，请稍后重试') from None

    @staticmethod
    async def update_toy(*, db: AsyncSession, pk: int, obj: UpdateToyParam) -> int:
        toy = await toy_dao.get(db, pk)
        if not toy:
            raise errors.NotFoundError(msg='玩偶不存在')

        payload = obj.model_dump(exclude_unset=True)
        if not payload:
            raise errors.RequestError(msg='更新内容不能为空')

        ToyService._validate_voice_binding(payload, current_toy=toy)
        if 'series_id' in payload:
            await ToyService._ensure_series_exists(db=db, series_id=payload['series_id'])
        if 'related_toy_ids' in payload:
            await ToyService._ensure_related_toys_exist(
                db=db,
                toy_ids=payload['related_toy_ids'],
                current_toy_id=pk,
            )
        try:
            count = await toy_dao.update(db, pk, payload)
            return count
        except IntegrityError:
            raise errors.ServerError(msg='更新玩偶失败，请稍后重试') from None

    @staticmethod
    async def delete_toy(*, db: AsyncSession, pk: int) -> int:
        toy = await toy_dao.get(db, pk)
        if not toy:
            raise errors.NotFoundError(msg='玩偶不存在')
        return await toy_dao.delete(db, pk)

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
                '[玩偶设定]',
                f'- 玩偶名称：{name}',
                f'- 玩偶简介：{summary}',
                '- 你的表达、情绪、关注点和常用说法，要稳定符合这个玩偶设定。',
                '- 如果简介信息不够完整，就用温暖、可信、适合儿童陪伴的方式自然补全。',
                '',
                '[上下文]',
                '- 你服务于儿童陪伴和家庭共学场景。',
                '- 用户有时是 5 到 9 岁的小朋友，有时是家长或老师替孩子提问。',
                '- 回答默认适合语音播报，所以要自然、顺口、短句、好懂。',
                '',
                '[目标]',
                '- 稳定扮演好这个玩偶角色，让用户感受到鲜明但自然的人设。',
                '- 支持知识讲解、互动聊天、讲故事、小游戏、简单写作和计划制定等常见任务。',
                '',
                '[风格]',
                '- 默认用短句，生动、有画面感，有陪伴感。',
                '- 先好懂，再有趣，最后再讲深一点。',
                '- 不装懂，不卖弄，不故意把简单问题说复杂。',
                '',
                '[语气]',
                '- 开心时灵动俏皮，安抚时温柔轻轻的，解释知识时耐心清楚。',
                '- 面对家长或老师时可以稍微更稳重，但不要失去亲切感。',
                '',
                '[响应]',
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
            '请基于以下玩偶信息和基础系统提示词，输出一版润色后的最终系统提示词。\n\n'
            f'玩偶名称：{name}\n'
            f'玩偶简介：{summary}\n\n'
            '润色要求：\n'
            '1. 保留原有结构、目标和安全边界，不要遗漏关键约束。\n'
            '2. 语言更自然、更顺口、更适合语音播报。\n'
            '3. 玩偶感要更稳定，儿童陪伴感更强，但不要过度夸张。\n'
            '4. 直接输出完整系统提示词正文，不要解释，不要代码块。\n\n'
            f'基础系统提示词：\n{template_prompt}'
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
            log.warning('润色玩偶系统提示词失败，将使用默认模板：玩偶名称={}，错误={}', name, exc)
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

    @staticmethod
    async def get_enabled_toy_id_by_tag_id(*, db: AsyncSession, tag_id: str) -> int:
        normalized_tag_id = ToyService._normalize_query_text(tag_id)
        if normalized_tag_id is None:
            raise errors.NotFoundError(msg='未找到对应玩偶，玩偶可能已禁用或标签无效')
        toy = await toy_dao.get_by_tag_id(db, tag_id=normalized_tag_id, enabled_only=True)
        if toy is None:
            raise errors.NotFoundError(msg='未找到对应玩偶，玩偶可能已禁用或标签无效')
        return int(toy.id)

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
            raise errors.RequestError(msg='声音服务商和声音 ID 必须同时为空或同时填写')


toy_service: ToyService = ToyService()
