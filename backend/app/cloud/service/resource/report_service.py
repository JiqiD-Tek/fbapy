# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : report_service.py
@Author  : OpenAI
@Date    : 2026/04/27
"""

from __future__ import annotations

import asyncio
import json

from datetime import date, datetime, time, timedelta
from typing import Any, ClassVar, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.crud_device import device_chat_dao
from backend.app.cloud.crud.resource.crud_script import script_dao
from backend.app.cloud.model import Baby
from backend.app.cloud.schema.resource.report import (
    PlaybackStat,
    ReportFeedback,
    ReportFeedbackSection,
    ReportRadarDimension,
    ReportTrendPoint,
    UsageReport,
)
from backend.app.cloud.service.baby_service import baby_service
from backend.app.cloud.telemetry.event_store import EventStore
from backend.common.exception import errors
from backend.common.log import log
from backend.common.providers.doubao import DEFAULT_DOUBAO_MINI_MODEL, doubao_provider
from backend.common.schema import SchemaBase
from backend.database.redis import redis_client
from backend.utils.timezone import timezone

CacheModelT = TypeVar('CacheModelT', bound=SchemaBase)
ACTIVE_DURATION_SECONDS = 300
DailyUsageStats = dict[str, Any]
ReportWindowData = dict[str, Any]


class ReportService:
    # 统计窗口与输入上限
    REPORT_DAYS: ClassVar[int] = 14
    REPORT_COMPARE_DAYS: ClassVar[int] = 7
    REPORT_QUERY_LIMIT: ClassVar[int] = 20000
    # 以下限制仅控制大模型输入，不影响业务统计。
    REPORT_INPUT_LIMIT: ClassVar[int] = 100
    REPORT_TEXT_LIMIT: ClassVar[int] = 500

    # 缓存配置
    USAGE_CACHE_PREFIX: ClassVar[str] = 'fba:report:usage'

    # 大模型提示词与输出结构
    REPORT_ANALYSIS_SYSTEM_PROMPT: ClassVar[str] = (
        '你是儿童成长报告分析助手。'
        '你的任务是根据输入数据生成稳定、保守、可直接解析的 JSON 结果。'
        '只输出 JSON，不要输出 Markdown、代码块、解释或额外文本。'
        '如果证据不足，使用保守判断，不要编造细节。'
        'current_week_radar 和 previous_week_radar 的 label 必须严格使用：表达、情感、专注、想象、逻辑。'
        '表达=口头表达、词汇使用与主动交流；情感=情绪表达与回应；专注=持续参与与注意保持；想象=联想、代入与创造表达；逻辑=因果理解、顺序组织与简单推理。'
        'value 范围只能是 0 到 100。'
        'current_week_radar 只依据本周数据，previous_week_radar 只依据上周数据。'
        '两组雷达数据必须分别评估，不要直接复制相同分数。'
        'notes 使用简短中文句子；advice 使用自然、具体、可执行的中文建议。'
        '面向用户描述时间范围时，只使用“本周”和“上周”，不要使用“最近 7 天”“前 7 天”、'
        '“最近7天”“前7天”“前一周”或“上一阶段”等表达。'
    )
    REPORT_OUTPUT_TEMPLATE: ClassVar[dict[str, Any]] = {
        'current_week_radar': [
            {'label': '表达', 'value': 0},
            {'label': '情感', 'value': 0},
            {'label': '专注', 'value': 0},
            {'label': '想象', 'value': 0},
            {'label': '逻辑', 'value': 0},
        ],
        'previous_week_radar': [
            {'label': '表达', 'value': 0},
            {'label': '情感', 'value': 0},
            {'label': '专注', 'value': 0},
            {'label': '想象', 'value': 0},
            {'label': '逻辑', 'value': 0},
        ],
        'feedback': {
            'overview': {'notes': [], 'advice': []},
            'interaction': {'notes': [], 'advice': []},
            'playback': {'notes': [], 'advice': []},
        },
    }

    # 防止同一进程内重复生成报告
    _usage_report_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    # 对外接口
    async def get_usage_report(
            self,
            *,
            db: AsyncSession,
            user_id: int,
            baby_id: int,
    ) -> UsageReport:
        baby = await baby_service.get(db=db, user_id=user_id, pk=baby_id)
        if baby is None:
            raise errors.NotFoundError(msg='宝宝不存在')

        cache_key = self._usage_report_cache_key(baby_id)
        cached_report = await self._get_cached_model(
            key=cache_key,
            baby_id=baby_id,
            label='使用报告',
            model_cls=UsageReport,
        )
        if cached_report is not None:
            return cached_report

        async with self._usage_report_lock:
            cached_report = await self._get_cached_model(
                key=cache_key,
                baby_id=baby_id,
                label='使用报告',
                model_cls=UsageReport,
            )
            if cached_report is not None:
                return cached_report

            report = await self._build_usage_report(db=db, baby=baby)
            return await self._set_cached_model(
                key=cache_key,
                baby_id=baby_id,
                label='使用报告',
                value=report,
            )

    # 缓存与时间窗口
    @classmethod
    def _resolve_report_window(cls) -> tuple[datetime, datetime]:
        today = timezone.now().date()
        end_time = datetime.combine(today, time.min, tzinfo=timezone.tz_info)
        start_date = today - timedelta(days=cls.REPORT_DAYS)
        start_time = datetime.combine(start_date, time.min, tzinfo=timezone.tz_info)
        return start_time, end_time

    @classmethod
    def _usage_report_cache_key(cls, baby_id: int) -> str:
        return f'{cls.USAGE_CACHE_PREFIX}:{baby_id}'

    @staticmethod
    def _resolve_cache_ttl_seconds() -> int:
        now = timezone.now()
        expires_at = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=timezone.tz_info)
        return max(int((expires_at - now).total_seconds()), 60)

    @classmethod
    async def _get_cached_model(
            cls,
            *,
            key: str,
            baby_id: int,
            label: str,
            model_cls: type[CacheModelT],
    ) -> CacheModelT | None:
        try:
            payload = await redis_client.get(key)
        except Exception as exc:
            log.warning('读取{}缓存失败，宝宝 ID={}，错误={}', label, baby_id, exc)
            return None

        if not payload:
            return None

        try:
            return model_cls.model_validate_json(payload)
        except Exception as exc:
            log.warning('解析{}缓存失败，宝宝 ID={}，错误={}', label, baby_id, exc)
            return None

    @classmethod
    async def _set_cached_model(
            cls,
            *,
            key: str,
            baby_id: int,
            label: str,
            value: CacheModelT,
    ) -> CacheModelT:
        try:
            await redis_client.set(
                key,
                value.model_dump_json(),
                ex=cls._resolve_cache_ttl_seconds(),
            )
        except Exception as exc:
            log.warning('写入{}缓存失败，宝宝 ID={}，错误={}', label, baby_id, exc)
        return value

    # 报告默认值、数据组装与提示词
    @staticmethod
    def _build_report_feedback() -> ReportFeedback:
        return ReportFeedback(
            overview=ReportFeedbackSection(
                notes=[
                    '这一阶段的使用记录还比较有限，孩子在整体成长表现上的变化还需要放在更连续的陪伴中慢慢观察。',
                ],
                advice=[
                    '先保持稳定、放松的陪伴节奏，在聊天、共读和游戏中多关注孩子愿意回应的内容。',
                ],
            ),
            interaction=ReportFeedbackSection(
                notes=[
                    '从目前有限的互动记录来看，孩子在表达、回应和持续参与上的表现，还需要更多日常互动来继续观察。',
                ],
                advice=[
                    '多采用开放式提问和轮流回应的方式，鼓励孩子多说一点、多回应一点。',
                ],
            ),
            playback=ReportFeedbackSection(
                notes=[
                    '现阶段可参考的收听记录还不多，孩子对内容类型和收听方式的偏好仍可以在后续陪伴中慢慢看见。',
                ],
                advice=[
                    '提供不同主题和节奏的内容，顺着孩子愿意重复收听的内容继续延展。',
                ],
            ),
        )

    @staticmethod
    def _build_default_report_sections(
    ) -> tuple[list[ReportRadarDimension], list[ReportRadarDimension], ReportFeedback]:
        return (
            [
                ReportRadarDimension.model_validate(item)
                for item in ReportService.REPORT_OUTPUT_TEMPLATE['current_week_radar']
            ],
            [
                ReportRadarDimension.model_validate(item)
                for item in ReportService.REPORT_OUTPUT_TEMPLATE['previous_week_radar']
            ],
            ReportService._build_report_feedback(),
        )

    @staticmethod
    def _build_trend(daily_stats: dict[date, DailyUsageStats]) -> list[ReportTrendPoint]:
        return [
            ReportTrendPoint(
                date=current_date.isoformat(),
                chat_count=usage['chat_count'],
                duration=usage['active_count'] * ACTIVE_DURATION_SECONDS,
                play_count=usage['play_count'],
                create_count=usage['create_count'],
            )
            for current_date, usage in daily_stats.items()
        ]

    @classmethod
    def _build_play_prefs(cls, daily_stats: dict[date, DailyUsageStats]) -> list[PlaybackStat]:
        play_prefs = cls._merge_daily_usage(daily_stats)['play_prefs']
        return [
            PlaybackStat(label=label, count=count)
            for label, count in sorted(play_prefs.items(), key=lambda item: (-item[1], item[0]))
        ]

    @classmethod
    def _build_llm_usage(
            cls,
            daily_stats: dict[date, DailyUsageStats],
            toy_counts: dict[int, int],
    ) -> dict[str, Any]:
        usage = cls._merge_daily_usage(daily_stats)
        return {
            'overview': {
                'chat_count': usage['chat_count'],
                'favorite_toy': cls._favorite_toy(toy_counts),
                'duration': usage['active_count'] * ACTIVE_DURATION_SECONDS,
                'play_count': usage['play_count'],
                'create_count': usage['create_count'],
                'play_prefs': [item.model_dump() for item in cls._build_play_prefs(daily_stats)],
            },
            'daily_activity': [item.model_dump() for item in cls._build_trend(daily_stats)],
        }

    @classmethod
    def _build_report_prompt(
            cls,
            *,
            baby_name: str,
            current_week_usage: dict[str, Any],
            previous_week_usage: dict[str, Any],
            current_week_user_messages: list[dict[str, str]],
            previous_week_user_messages: list[dict[str, str]],
            current_week_story_topics: list[dict[str, str]],
            previous_week_story_topics: list[dict[str, str]],
    ) -> str:
        def encode(value: Any) -> str:
            return json.dumps(value, ensure_ascii=False, separators=(',', ':'))

        return f'''你是儿童成长报告分析助手，请根据下方事实生成一份简洁、审慎、可执行的成长报告。

【宝宝信息】
宝宝称呼：{baby_name}

【分析任务】
1. 对比本周与上周的变化，判断趋势时优先依据使用统计数据。
2. feedback.overview 分析整体成长表现，feedback.interaction 分析用户与 AI 的互动表现，feedback.playback 分析内容播放偏好。
3. 用户聊天内容用于了解用户主动表达和兴趣；AI 故事创作主题用于了解用户提出过的创作方向。

【数据来源与事实边界】
- 使用统计来自时序数据库。
- 用户聊天内容来自 device_chat.content.user_message，每条包含 time 和 content。
- 故事创作主题来自 script.remark，每条包含 time 和 topic。
- 故事创作主题只表示用户发起过创作请求，不表示故事已经播放或听完。
- 只能使用输入中的事实，不要根据玩偶 ID、主题或单条消息臆测用户的年龄、性格、家庭情况或发展结论。
- 数据为空、样本较少或前后差异不足时，使用保守表述和保守评分。

【输出要求】
- 只输出 JSON，不要输出 Markdown、解释、代码块或额外文字。
- JSON 顶层只能包含 current_week_radar、previous_week_radar、feedback 三个字段，结构必须严格参考下面的模板。
- current_week_radar 表示本周，previous_week_radar 表示上周，两组数据必须独立依据对应时间段进行评估。
- 两组雷达数据必须各包含五个维度，label 只能使用：表达、情感、专注、想象、逻辑。
- 所有 value 必须是 0 到 100 的整数。
- 每个 notes 输出 1 到 2 条简短中文句子；每个 advice 输出 1 条具体、自然、可执行的中文建议。
- 数据不足时可表述为“本周暂无相关记录”或“上周暂无相关记录，因此暂不能判断变化”。
- 不要在 JSON 中增加模板之外的字段，不要输出 favorite_toy 等原始统计字段。

【JSON 模板】
{encode(cls.REPORT_OUTPUT_TEMPLATE)}

【本周数据】
使用统计：{encode(current_week_usage)}
用户聊天内容：{encode(current_week_user_messages)}
AI 故事创作主题：{encode(current_week_story_topics)}

【上周数据】
使用统计：{encode(previous_week_usage)}
用户聊天内容：{encode(previous_week_user_messages)}
AI 故事创作主题：{encode(previous_week_story_topics)}
'''

    # 报告构建主流程
    async def _build_usage_report(
            self,
            *,
            db: AsyncSession,
            baby: Baby,
    ) -> UsageReport:
        start_time, end_time = self._resolve_report_window()
        current_week_start = start_time + timedelta(days=self.REPORT_COMPARE_DAYS)
        previous_data, current_data = await asyncio.gather(
            self._query_window_data(
                db=db,
                baby_id=baby.id,
                start_time=start_time,
                end_time=current_week_start,
            ),
            self._query_window_data(
                db=db,
                baby_id=baby.id,
                start_time=current_week_start,
                end_time=end_time,
            ),
        )
        previous_week_user_messages = previous_data['user_messages']
        current_week_user_messages = current_data['user_messages']
        previous_week_story_topics = previous_data['story_topics']
        current_week_story_topics = current_data['story_topics']
        current_week_usage = self._build_llm_usage(current_data['daily_stats'], current_data['toy_counts'])
        previous_week_usage = self._build_llm_usage(previous_data['daily_stats'], previous_data['toy_counts'])
        has_source_records = any((
            current_week_user_messages,
            previous_week_user_messages,
            current_week_story_topics,
            previous_week_story_topics,
        ))
        current_week_radar, previous_week_radar, feedback = await self._build_by_llm(
            baby_id=baby.id,
            baby_name=baby.name or '宝贝',
            current_week_usage=current_week_usage,
            previous_week_usage=previous_week_usage,
            current_week_user_messages=current_week_user_messages,
            previous_week_user_messages=previous_week_user_messages,
            current_week_story_topics=current_week_story_topics,
            previous_week_story_topics=previous_week_story_topics,
            has_activity=self._has_activity(current_data['daily_stats']) or self._has_activity(
                previous_data['daily_stats'],
            ) or has_source_records,
        )

        return UsageReport(
            current_week_radar=current_week_radar,
            previous_week_radar=previous_week_radar,
            current_week_trend=self._build_trend(current_data['daily_stats']),
            previous_week_trend=self._build_trend(previous_data['daily_stats']),
            playback_stats=self._build_play_prefs(current_data['daily_stats']),
            feedback=feedback,
        )

    @classmethod
    def _limit_text(cls, value: Any) -> str:
        text = str(value or '').strip()
        return text[:cls.REPORT_TEXT_LIMIT]

    @staticmethod
    def _new_daily_usage() -> DailyUsageStats:
        return {
            'chat_count': 0,
            'active_count': 0,
            'play_count': 0,
            'create_count': 0,
            'play_prefs': {},
            'toy_counts': {},
        }

    @classmethod
    def _aggregate_daily_usage(
            cls,
            rows: list[dict[str, Any]],
            start_date: date,
            end_date: date,
    ) -> dict[date, DailyUsageStats]:
        daily_usage = {
            start_date + timedelta(days=offset): cls._new_daily_usage()
            for offset in range((end_date - start_date).days)
        }
        for row in rows:
            event_time = row.get('ts')
            if not isinstance(event_time, datetime) or not start_date <= event_time.date() < end_date:
                continue
            usage = daily_usage.setdefault(event_time.date(), cls._new_daily_usage())
            service = str(row.get('service') or '').strip().lower()
            if service == 'active':
                usage['active_count'] += 1
            elif service != 'play':
                continue
            else:
                usage['play_count'] += 1
                payload = row.get('payload')
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError:
                        payload = None
                if isinstance(payload, dict) and payload.get('content_type'):
                    label = {1: '语言', 2: '科学', 3: '社会', 4: '艺术', 5: '健康'}.get(
                        payload['content_type'], '创作',
                    )
                    usage['play_prefs'][label] = usage['play_prefs'].get(label, 0) + 1
        return daily_usage

    # 数据源查询
    @classmethod
    async def _query_usage_rows(
            cls,
            *,
            baby_id: int,
            start_time: datetime,
            end_time: datetime,
            model: str = 'js61',
    ) -> list[dict[str, Any]]:
        try:
            return await EventStore.query(
                model=model,
                baby_id=baby_id,
                start_time=start_time,
                end_time=end_time,
                limit=cls.REPORT_QUERY_LIMIT,
            )
        except Exception as exc:
            log.warning('查询时序数据库使用记录失败，宝宝 ID={}，错误={}', baby_id, exc)
            return []

    @classmethod
    async def _query_window_data(
            cls,
            *,
            db: AsyncSession,
            baby_id: int,
            start_time: datetime,
            end_time: datetime,
    ) -> ReportWindowData:
        rows, chat_records, generated_scripts = await asyncio.gather(
            cls._query_usage_rows(
                baby_id=baby_id, start_time=start_time, end_time=end_time,
            ),
            cls._query_chat_records(
                db=db, baby_id=baby_id, start_time=start_time, end_time=end_time,
            ),
            cls._query_generated_scripts(
                db=db, baby_id=baby_id, start_time=start_time, end_time=end_time,
            ),
        )
        daily_stats = cls._aggregate_daily_usage(rows, start_time.date(), end_time.date())
        for created_time, _, toy_ids in chat_records:
            usage = daily_stats.get(created_time.date())
            if usage is None:
                continue
            usage['chat_count'] += 1
            for toy_id in toy_ids:
                usage['toy_counts'][toy_id] = usage['toy_counts'].get(toy_id, 0) + 1
        for created_time, _ in generated_scripts:
            usage = daily_stats.get(created_time.date())
            if usage is not None:
                usage['create_count'] += 1

        return {
            'daily_stats': daily_stats,
            'user_messages': cls._format_user_messages(chat_records),
            'toy_counts': cls._count_toys(chat_records),
            'story_topics': cls._format_story_topics(generated_scripts),
        }

    @classmethod
    async def _query_chat_records(
            cls,
            *,
            db: AsyncSession,
            baby_id: int,
            start_time: datetime,
            end_time: datetime,
    ) -> list[tuple[datetime, str | None, list[int]]]:
        try:
            records = await device_chat_dao.get_contents_by_time_range(
                db,
                baby_id=baby_id,
                start_time=start_time,
                end_time=end_time,
                limit=None,
            )
            chat_records: list[tuple[datetime, str | None, list[int]]] = []
            for created_time, raw_content in records:
                content = raw_content if isinstance(raw_content, dict) else {}
                user_message = cls._limit_text(content.get('user_message'))
                toy_ids: list[int] = []
                replies = content.get('replies')
                if isinstance(replies, list):
                    for reply in replies:
                        if not isinstance(reply, dict) or isinstance(reply.get('toy_id'), bool):
                            continue
                        try:
                            toy_id = int(reply.get('toy_id'))
                        except (TypeError, ValueError):
                            continue
                        if toy_id > 0:
                            toy_ids.append(toy_id)
                chat_records.append((created_time, user_message or None, toy_ids))
            return sorted(chat_records, key=lambda item: item[0])
        except Exception as exc:
            log.warning('查询设备聊天数据失败，宝宝 ID={}，错误={}', baby_id, exc)
            return []

    @classmethod
    def _format_user_messages(
            cls,
            records: list[tuple[datetime, str | None, list[int]]],
    ) -> list[dict[str, str]]:
        messages = [
            {'time': created_time.isoformat(timespec='seconds'), 'content': message}
            for created_time, message, _ in records
            if message
        ]
        return messages[-cls.REPORT_INPUT_LIMIT:]

    @classmethod
    def _count_toys(
            cls,
            records: list[tuple[datetime, str | None, list[int]]],
    ) -> dict[int, int]:
        counts: dict[int, int] = {}
        for _, _, toy_ids in records:
            for toy_id in toy_ids:
                counts[toy_id] = counts.get(toy_id, 0) + 1
        return counts

    @staticmethod
    def _favorite_toy(toy_counts: dict[int, int]) -> int | None:
        return min(toy_counts, key=lambda toy_id: (-toy_counts[toy_id], toy_id), default=None)

    @classmethod
    async def _query_generated_scripts(
            cls,
            *,
            db: AsyncSession,
            baby_id: int,
            start_time: datetime,
            end_time: datetime,
    ) -> list[tuple[datetime, str | None]]:
        try:
            records = await script_dao.get_generated_topics_by_time_range(
                db,
                baby_id=baby_id,
                start_time=start_time,
                end_time=end_time,
                limit=None,
            )
            return list(records)
        except Exception as exc:
            log.warning('查询宝宝的 AI 剧本创作记录失败，宝宝 ID={}，错误={}', baby_id, exc)
            return []

    @classmethod
    def _format_story_topics(
            cls,
            records: list[tuple[datetime, str | None]],
    ) -> list[dict[str, str]]:
        story_topics: list[dict[str, str]] = []
        for created_time, remark in reversed(records[:cls.REPORT_INPUT_LIMIT]):
            topic = cls._limit_text(remark)
            if topic:
                story_topics.append({
                    'time': created_time.isoformat(timespec='seconds'),
                    'topic': topic,
                })
        return story_topics

    # 大模型生成与结果解析
    @classmethod
    async def _build_by_llm(
            cls,
            *,
            baby_id: int,
            baby_name: str,
            current_week_usage: dict[str, Any],
            previous_week_usage: dict[str, Any],
            current_week_user_messages: list[dict[str, str]],
            previous_week_user_messages: list[dict[str, str]],
            current_week_story_topics: list[dict[str, str]],
            previous_week_story_topics: list[dict[str, str]],
            has_activity: bool,
    ) -> tuple[list[ReportRadarDimension], list[ReportRadarDimension], ReportFeedback]:
        if not has_activity:
            return cls._build_default_report_sections()

        try:
            llm_content = await cls._generate_by_llm(
                baby_name=baby_name,
                current_week_usage=current_week_usage,
                previous_week_usage=previous_week_usage,
                current_week_user_messages=current_week_user_messages,
                previous_week_user_messages=previous_week_user_messages,
                current_week_story_topics=current_week_story_topics,
                previous_week_story_topics=previous_week_story_topics,
            )
            return cls._parse_llm_response(llm_content)
        except Exception as exc:
            log.warning('生成大模型报告分析失败，宝宝 ID={}，错误={}', baby_id, exc)
            return cls._build_default_report_sections()

    @classmethod
    async def _generate_by_llm(
            cls,
            *,
            baby_name: str,
            current_week_usage: dict[str, Any],
            previous_week_usage: dict[str, Any],
            current_week_user_messages: list[dict[str, str]],
            previous_week_user_messages: list[dict[str, str]],
            current_week_story_topics: list[dict[str, str]],
            previous_week_story_topics: list[dict[str, str]],
    ) -> str:
        prompt = cls._build_report_prompt(
            baby_name=baby_name,
            current_week_usage=current_week_usage,
            previous_week_usage=previous_week_usage,
            current_week_user_messages=current_week_user_messages,
            previous_week_user_messages=previous_week_user_messages,
            current_week_story_topics=current_week_story_topics,
            previous_week_story_topics=previous_week_story_topics,
        )
        return await doubao_provider.chat(
            [
                {'role': 'system', 'content': cls.REPORT_ANALYSIS_SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt},
            ],
            model_name=DEFAULT_DOUBAO_MINI_MODEL,
            reasoning_effort='minimal',
            temperature=0.1,
        )

    @classmethod
    def _parse_llm_response(
            cls,
            content: str,
    ) -> tuple[list[ReportRadarDimension], list[ReportRadarDimension], ReportFeedback]:
        fallback_current_radar, fallback_previous_radar, fallback_feedback = cls._build_default_report_sections()

        if not content:
            return fallback_current_radar, fallback_previous_radar, fallback_feedback

        try:
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError('报告分析结果必须是 JSON 对象')

            current_radar_data = payload.get('current_week_radar')
            previous_radar_data = payload.get('previous_week_radar')
            feedback_data = payload.get('feedback')

            current_week_radar = (
                [ReportRadarDimension.model_validate(item) for item in current_radar_data]
                if isinstance(current_radar_data, list) and current_radar_data
                else fallback_current_radar
            )
            previous_week_radar = (
                [ReportRadarDimension.model_validate(item) for item in previous_radar_data]
                if isinstance(previous_radar_data, list) and previous_radar_data
                else fallback_previous_radar
            )
            feedback = (
                ReportFeedback.model_validate(feedback_data)
                if isinstance(feedback_data, dict)
                else fallback_feedback
            )
            return current_week_radar, previous_week_radar, feedback
        except Exception as exc:
            log.warning('解析大模型报告分析结果失败，错误={}', exc)
            return fallback_current_radar, fallback_previous_radar, fallback_feedback

    # 统计辅助方法
    @staticmethod
    def _has_activity(daily_stats: dict[date, DailyUsageStats]) -> bool:
        return any(
            usage['chat_count'] + usage['active_count'] + usage['play_count'] > 0
            for usage in daily_stats.values()
        )

    @classmethod
    def _merge_daily_usage(cls, daily_stats: dict[date, DailyUsageStats]) -> DailyUsageStats:
        merged_usage = cls._new_daily_usage()
        for daily_usage in daily_stats.values():
            merged_usage['chat_count'] += daily_usage['chat_count']
            merged_usage['active_count'] += daily_usage['active_count']
            merged_usage['play_count'] += daily_usage['play_count']
            merged_usage['create_count'] += daily_usage['create_count']
            for label, count in daily_usage['play_prefs'].items():
                merged_usage['play_prefs'][label] = merged_usage['play_prefs'].get(label, 0) + count
            for toy_id, count in daily_usage['toy_counts'].items():
                merged_usage['toy_counts'][toy_id] = merged_usage['toy_counts'].get(toy_id, 0) + count
        return merged_usage


report_service: ReportService = ReportService()
