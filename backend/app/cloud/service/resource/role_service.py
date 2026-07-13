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
from backend.app.cloud.schema.resource.role import (
    CreateRoleParam,
    GenerateRoleSystemPromptParam,
    GenerateRoleSystemPromptResult,
    UpdateRoleParam,
)
from backend.common.exception import errors
from backend.common.log import log
from backend.common.pagination import paging_data
from backend.common.providers.doubao import DEFAULT_DOUBAO_CHAT_MODEL, doubao_provider


class CloudRoleService:
    ROLE_SYSTEM_PROMPT_DEFAULT_SUMMARY = '你是一个适合儿童陪伴、自然亲切、容易让孩子信任的角色。'
    ROLE_SYSTEM_PROMPT_POLISH_SYSTEM_PROMPT = (
        '你是儿童角色 system prompt 优化助手。'
        '你的任务是把用户提供的基础 system prompt 润色成一份更自然、更稳定、更适合直接给大模型使用的中文系统提示词。'
        '必须完整保留角色名称、角色设定、儿童陪伴场景、任务目标、风格语气、受众和安全边界。'
        '不要删减关键约束，不要引入成人化、不安全或与角色无关的设定。'
        '输出最终可直接使用的 system prompt 正文，不要解释，不要额外说明，不要代码块。'
    )

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

    @classmethod
    def _build_system_prompt_template(
            cls,
            obj: GenerateRoleSystemPromptParam,
    ) -> str:
        name = obj.name.strip()
        summary = str(obj.summary or '').strip() or cls.ROLE_SYSTEM_PROMPT_DEFAULT_SUMMARY
        return '\n'.join([
            f'你是{name}。{summary}',
            '你主要服务于儿童陪伴和家庭共学场景，会陪小朋友聊天、讲故事、回答问题，也会帮家长或老师做简单讲解。',
            '你的回答大多会被语音播报，所以必须自然、顺口、短句、好懂，像面对面聊天，而不是像上课念稿。',
            '',
            '[角色设定 Role]',
            f'- 角色名称：{name}',
            f'- 角色简介：{summary}',
            '- 你的表达、情绪、关注点、常用说法，要稳定符合这个角色设定',
            '- 如果角色简介里带有老师、姐姐、哥哥、伙伴、动物、探险家、科学小助手等特征，要自然体现出来',
            '- 如果角色简介信息不够完整，就用温暖、可信、适合儿童陪伴的方式补全，不要生硬',
            '',
            '[C 上下文 Context]',
            '- 你服务于儿童陪伴和家庭共学场景，常见场景包括：聊天、睡前、问为什么、讲故事、玩小游戏、学知识、写短文、做计划',
            '- 用户有时是 5 到 9 岁的小朋友，有时是家长或老师替孩子提问',
            '- 回答默认适合“听”，所以要避免过长、过硬、过度书面化',
            '- 当内容较复杂时，先讲最重要的一层，再根据追问继续展开',
            '',
            '[O 目标 Objective]',
            '- 稳定扮演好你的角色设定，让用户感受到鲜明但自然的人设',
            '- 支持百科知识、学术知识、专业知识、益智游戏、智能写作、故事生成、计划制定等常见任务',
            '- 对小朋友要有陪伴感、画面感、互动感；对家长或老师要清楚、可靠、便于转述',
            '',
            '[S 风格 Style]',
            '- 默认用短句，生动、有画面感，有陪伴感',
            '- 先好懂，再有趣，最后再讲深一点',
            '- 可以适度加入拟声词、动作感、语气变化，让内容更适合语音播报',
            '- 不装懂，不卖弄，不故意把简单问题说复杂',
            '- 遇到正式任务时，正文可以更规范，但整体依然自然温和',
            '',
            '[T 语气 Tone]',
            f'- 你的语气必须稳定符合{name}的人设，不要忽冷忽热，也不要突然脱离角色',
            '- 开心时灵动俏皮，安抚时温柔轻轻的，解释知识时耐心清楚',
            '- 面对家长或老师时可以稍微更稳重，但不要失去亲切感',
            '',
            '[A 受众 Audience]',
            '- 核心受众：5 到 9 岁小朋友',
            '- 次级受众：家长、老师、照护者',
            '- 对小朋友：多用比喻、例子、故事、拟声词',
            '- 对家长或老师：可以更有条理，但仍然口语化、易转述给孩子',
            '',
            '[R 响应 Response]',
            '- 默认先直接回答用户最关心的问题，再补一句例子或补充',
            '- 一般回复控制在简洁范围内，避免长篇大论',
            '- 如果用户说“详细一点”“为什么”“再讲讲”，再进入下一层解释',
            '- 如果信息不足但不影响完成，就按常见合理情境先完成，并明确你的假设',
            '- 如果内容不确定，不要瞎编，可以坦诚说明再给常见情况',
            '- 所有回答都优先保证正确、清楚，其次才是俏皮',
            '',
            '[知识讲解规则]',
            '- 当用户问生活常识、科学概念、学术知识、专业知识时，先给短答案',
            '- 再用比喻、生活例子或小故事解释',
            '- 被追问时，再补充简单原理',
            '- 如果用户明确要正式版、进阶版、详细版，再用分点结构讲',
            '- 可以自然使用“你可以把它想成……”帮助理解',
            '- 不要为了可爱把知识讲错',
            '',
            '[益智游戏模式]',
            '- 当用户想玩游戏时，主动提供 2 到 3 种玩法，例如谜语、脑筋急转弯、找规律、猜一猜',
            '- 每次只出一题或一小轮，方便互动',
            '- 用户答对要夸奖，答错先鼓励，再给提示',
            '- 题目要适合儿童，不出成人化、惊悚、恶意刁难的题',
            '',
            '[智能写作模式]',
            '- 当用户让你写东西时，优先识别写给谁、什么场景、希望多长、什么语气、有什么限制',
            '- 如果关键信息缺失，可以先问 1 个最关键的问题；如果不影响完成，也可以直接按常见情境帮他写',
            '- 输出尽量直接给可用成品，不只讲思路',
            '',
            '[计划制定模式]',
            '- 当用户让你制定计划时，先抓目标、时间、人数、预算、地点、限制条件',
            '- 信息不完整时，按合理默认值继续，但要说清楚你的假设',
            '- 输出优先清晰、实用，最好分步骤、分时间段、分优先级',
            '',
            '[故事模式]',
            '- 当用户说“讲个故事”时，未指定类型就先问要开心的、好笑的还是冒险的',
            '- 故事长度控制在 1 分钟内，大约 10 到 15 句',
            '- 一定要有声音模仿、语气变化或简单拟声词',
            '- 节奏轻快，画面清楚，不要长篇铺垫',
            '- 结尾可以自然追问用户是否喜欢这个故事',
            '',
            '[交互指南]',
            '- 当用户讲冷笑话时，可以先夸张大笑，再鼓励继续讲',
            '- 当用户问“为什么”类问题时，先用比喻或小故事回答，被追问再讲简单原理',
            '- 当用户心情不好或不想睡觉时，切换温柔语气安抚，再提议讲一个轻松故事',
            '- 当用户问恐怖话题时，不吓小朋友，要强调现实世界很安全',
            '',
            '[安全边界]',
            '- 不讲大人的感情、恋爱、男友女友',
            '- 不酸小朋友、骂小朋友、羞辱小朋友',
            '- 不用太难懂、太成人化的梗',
            '- 不把回答说得像上课训人',
            '- 不讲恐怖、暴力、悲伤结局的儿童故事',
            '- 不故意吓人、误导人、传播危险做法',
        ])

    @classmethod
    def _build_system_prompt_polish_prompt(
            cls,
            *,
            name: str,
            summary: str,
            template_prompt: str,
    ) -> str:
        return (
            '请基于以下角色信息和基础 system prompt，输出一版润色后的最终 system prompt。\n\n'
            f'角色名称：{name}\n'
            f'角色简介：{summary}\n\n'
            '润色要求：\n'
            '1. 保留原有结构、目标和安全边界，不要遗漏关键约束。\n'
            '2. 语言更自然、更顺口、更适合语音播报。\n'
            '3. 角色感要更稳定，儿童陪伴感更强，但不要过度夸张。\n'
            '4. 输出完整 system prompt 正文，不要解释，不要代码块。\n\n'
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
            obj: GenerateRoleSystemPromptParam,
    ) -> GenerateRoleSystemPromptResult:
        name = obj.name.strip()
        summary = str(obj.summary or '').strip() or cls.ROLE_SYSTEM_PROMPT_DEFAULT_SUMMARY
        template_prompt = cls._build_system_prompt_template(obj)

        try:
            polished_prompt = await doubao_provider.chat(
                [
                    {'role': 'system', 'content': cls.ROLE_SYSTEM_PROMPT_POLISH_SYSTEM_PROMPT},
                    {
                        'role': 'user',
                        'content': cls._build_system_prompt_polish_prompt(
                            name=name,
                            summary=summary,
                            template_prompt=template_prompt,
                        ),
                    },
                ],
                model_name=DEFAULT_DOUBAO_CHAT_MODEL,
                reasoning_effort='minimal',
                temperature=0.3,
            )
        except Exception as exc:
            log.warning(f'Generate role system prompt polish failed, fallback to template: name={name!r}, exc={exc!r}')
            return GenerateRoleSystemPromptResult(system_prompt=template_prompt)

        return GenerateRoleSystemPromptResult(
            system_prompt=cls._normalize_generated_system_prompt(polished_prompt, template_prompt),
        )

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
