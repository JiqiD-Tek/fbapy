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

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, ClassVar, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.model import Baby
from backend.app.cloud.schema.resource.report import (
    ActivityTrendPoint,
    PlayPreferenceStat,
    ReportInsight,
    ReportInsights,
    ReportMetric,
    ReportRadarPoint,
    UsageReport,
    UsageReportPreview,
    UsagePreviewOverview,
    UsagePreviewSection,
)
from backend.app.cloud.service.baby_service import baby_service
from backend.app.cloud.timeseries.event_store import EventStore
from backend.common.exception import errors
from backend.common.log import log
from backend.common.providers.doubao import DEFAULT_DOUBAO_CHAT_MODEL, doubao_provider
from backend.common.providers.viking_memory import viking_memory_client
from backend.common.schema import SchemaBase
from backend.database.redis import redis_client
from backend.utils.timezone import timezone

CacheModelT = TypeVar('CacheModelT', bound=SchemaBase)
ACTIVE_DURATION_SECONDS = 300


@dataclass(slots=True)
class UsageCounter:
    chat_count: int = 0
    active_count: int = 0
    player_count: int = 0
    play_preferences: dict[str, int] = field(default_factory=dict)

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or '').strip().lower()

    @staticmethod
    def _parse_payload(payload: Any) -> dict[str, Any] | None:
        if isinstance(payload, dict):
            return payload
        if not isinstance(payload, str):
            return None

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None

        return data if isinstance(data, dict) else None

    @classmethod
    def _resolve_play_preference(cls, row: dict[str, Any], service: str) -> str | None:
        if service != 'player':
            return None

        payload = cls._parse_payload(row.get('payload'))
        if payload is None:
            return None

        nested_payload = payload.get('payload')
        if not isinstance(nested_payload, dict):
            return None

        value = nested_payload.get('category')
        if not value:
            return None

        return str(value).strip() or None

    @staticmethod
    def _resolve_event_date(row: dict[str, Any]) -> date | None:
        event_time = row.get('ts')
        if not isinstance(event_time, datetime):
            return None
        return event_time.date()

    @classmethod
    def _resolve_row(cls, row: dict[str, Any]) -> tuple[date | None, str, str | None]:
        service = cls._normalize_text(row.get('service'))
        event_date = cls._resolve_event_date(row)
        play_preference = cls._resolve_play_preference(row, service)
        return event_date, service, play_preference

    def add(self, service: str, *, play_preference: str | None = None) -> None:
        if service == 'chat':
            self.chat_count += 1
        elif service == 'active':
            self.active_count += 1
        elif service == 'player':
            self.player_count += 1
            if play_preference:
                self.play_preferences[play_preference] = self.play_preferences.get(play_preference, 0) + 1

    def to_trend_point(self, current_date: date) -> ActivityTrendPoint:
        return ActivityTrendPoint(
            date=current_date.isoformat(),
            chat_count=self.chat_count,
            duration=self.active_count * ACTIVE_DURATION_SECONDS,
            player_count=self.player_count,
        )

    def to_play_preferences(self) -> list[PlayPreferenceStat]:
        return [
            PlayPreferenceStat(label=label, count=count)
            for label, count in sorted(self.play_preferences.items(), key=lambda item: (-item[1], item[0]))
        ]

    @classmethod
    def aggregate_rows(
            cls,
            rows: list[dict[str, Any]],
            dates: list[date],
    ) -> dict[date, UsageCounter]:
        daily_counters = {current_date: cls() for current_date in dates}

        for row in rows:
            event_date, service, play_preference = cls._resolve_row(row)
            if event_date is None or event_date not in daily_counters:
                continue

            daily_counters[event_date].add(service, play_preference=play_preference)

        return daily_counters


class ReportService:
    REPORT_DAYS: ClassVar[int] = 14
    REPORT_COMPARE_DAYS: ClassVar[int] = 7
    REPORT_QUERY_LIMIT: ClassVar[int] = 20000
    REPORT_ANALYSIS_SYSTEM_PROMPT: ClassVar[str] = (
        '你是儿童成长报告分析助手。'
        '你的任务是根据输入数据生成稳定、保守、可直接解析的 JSON 结果。'
        '只输出 JSON，不要输出 Markdown、代码块、解释或额外文本。'
        '如果证据不足，使用保守判断，不要编造细节，trend 优先使用 flat。'
        'radar 和 metrics 的 label 必须严格使用：表达、情感、专注、想象、逻辑。'
        '表达=口头表达、词汇使用与主动交流；情感=情绪表达与回应；专注=持续参与与注意保持；'
        '想象=联想、代入与创造表达；逻辑=因果理解、顺序组织与简单推理。'
        'value 范围只能是 0 到 100；trend 只能是 up、down、flat。'
        'metrics.value 和 radar.value 主要依据最近一周数据；metrics.trend 依据最近一周相对前一周的变化。'
        'observations 使用简短中文句子；suggestion 只写一条自然、具体、可执行的建议。'
    )
    REPORT_OUTPUT_TEMPLATE: ClassVar[dict[str, Any]] = {
        'radar': [
            {'label': '表达', 'value': 0},
            {'label': '情感', 'value': 0},
            {'label': '专注', 'value': 0},
            {'label': '想象', 'value': 0},
            {'label': '逻辑', 'value': 0},
        ],
        'metrics': [
            {'label': '表达', 'value': 0, 'trend': 'flat'},
            {'label': '情感', 'value': 0, 'trend': 'flat'},
            {'label': '专注', 'value': 0, 'trend': 'flat'},
            {'label': '想象', 'value': 0, 'trend': 'flat'},
            {'label': '逻辑', 'value': 0, 'trend': 'flat'},
        ],
        'insights': {
            'summary': {'observations': [], 'suggestion': ''},
            'interaction': {'observations': [], 'suggestion': ''},
            'playback': {'observations': [], 'suggestion': ''},
        },
    }

    USAGE_CACHE_PREFIX: ClassVar[str] = 'fba:report:usage'
    PREVIEW_CACHE_PREFIX: ClassVar[str] = 'fba:report:preview'
    _usage_report_lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _usage_preview_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    def _resolve_report_window(cls) -> tuple[datetime, datetime, list[date]]:
        today = timezone.now().date()
        end_time = datetime.combine(today, time.min, tzinfo=timezone.tz_info)
        start_date = today - timedelta(days=cls.REPORT_DAYS)
        start_time = datetime.combine(start_date, time.min, tzinfo=timezone.tz_info)
        dates = [start_date + timedelta(days=offset) for offset in range(cls.REPORT_DAYS)]
        return start_time, end_time, dates

    @classmethod
    def _usage_preview_cache_key(cls, baby_id: int) -> str:
        return f'{cls.PREVIEW_CACHE_PREFIX}:{baby_id}'

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
            log.warning('failed to read {} cache, baby_id={}, error={}', label, baby_id, exc)
            return None

        if not payload:
            return None

        try:
            return model_cls.model_validate_json(payload)
        except Exception as exc:
            log.warning('failed to parse {} cache, baby_id={}, error={}', label, baby_id, exc)
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
            log.warning('failed to write {} cache, baby_id={}, error={}', label, baby_id, exc)
        return value

    @staticmethod
    def _build_report_insights() -> ReportInsights:
        return ReportInsights(
            summary=ReportInsight(
                observations=[
                    '这一阶段的使用记录还比较有限，孩子在整体成长表现上的变化还需要放在更连续的陪伴中慢慢观察。',
                ],
                suggestion='先保持稳定、放松的陪伴节奏，在聊天、共读和游戏中多关注孩子愿意回应的内容，让成长信号在日常互动中慢慢积累起来。',
            ),
            interaction=ReportInsight(
                observations=[
                    '从目前有限的互动记录来看，孩子在表达、回应和持续参与上的表现，还需要更多日常互动来继续观察。',
                ],
                suggestion='多采用开放式提问和轮流回应的方式，先接住孩子当下的表达，再在有安全感的互动中慢慢鼓励他多说一点、多回应一点。',
            ),
            playback=ReportInsight(
                observations=[
                    '现阶段可参考的收听记录还不多，孩子对内容类型和收听方式的偏好仍可以在后续陪伴中慢慢看见。',
                ],
                suggestion='提供不同主题和节奏的内容让孩子自然接触，顺着他愿意停留和重复收听的内容继续延展，逐步观察兴趣和偏好的变化。',
            ),
        )

    @staticmethod
    def _build_default_report_sections(
    ) -> tuple[list[ReportRadarPoint], list[ReportMetric], ReportInsights]:
        return (
            [ReportRadarPoint.model_validate(item) for item in ReportService.REPORT_OUTPUT_TEMPLATE['radar']],
            [ReportMetric.model_validate(item) for item in ReportService.REPORT_OUTPUT_TEMPLATE['metrics']],
            ReportService._build_report_insights(),
        )

    @staticmethod
    def _build_preview_overview(counter: UsageCounter) -> UsagePreviewOverview:
        return UsagePreviewOverview(
            chat_count=counter.chat_count,
            duration=counter.active_count * ACTIVE_DURATION_SECONDS,
            player_count=counter.player_count,
            play_preferences=counter.to_play_preferences(),
        )

    @classmethod
    def _build_preview_section(cls, daily_counters: dict[date, UsageCounter]) -> UsagePreviewSection:
        counter = cls._sum_daily_counters(daily_counters)
        return UsagePreviewSection(
            overview=cls._build_preview_overview(counter),
            daily_activity=[
                item.to_trend_point(current_date)
                for current_date, item in daily_counters.items()
            ],
        )

    @staticmethod
    def _section_has_activity(section: UsagePreviewSection) -> bool:
        overview = section.overview
        return (overview.chat_count + overview.duration + overview.player_count) > 0

    @staticmethod
    def _section_to_llm_usage(section: UsagePreviewSection) -> dict[str, Any]:
        return {
            'overview': {
                'chat_count': section.overview.chat_count,
                'duration': section.overview.duration,
                'player_count': section.overview.player_count,
                'play_preferences': [item.model_dump() for item in section.overview.play_preferences],
            },
            'daily_activity': [item.model_dump() for item in section.daily_activity],
        }

    @classmethod
    def _build_report_prompt(
            cls,
            *,
            baby_name: str,
            current_week_usage: dict[str, Any],
            previous_week_usage: dict[str, Any],
            current_week_viking_report: str,
            previous_week_viking_report: str,
    ) -> str:
        output_template = json.dumps(cls.REPORT_OUTPUT_TEMPLATE, ensure_ascii=False)
        current_week_usage_text = json.dumps(current_week_usage, ensure_ascii=False)
        previous_week_usage_text = json.dumps(previous_week_usage, ensure_ascii=False)
        return (
            f'输出 JSON 结构：{output_template}'
            '请结合两周使用数据和两周画像摘要生成结果。'
            '优先使用输入中的事实，证据不足时保持保守。'
            'summary 聚焦整体成长观察，interaction 聚焦互动表现，playback 聚焦收听偏好。'
            '每个 observations 写 1 到 2 条短句；每个 suggestion 只写 1 条建议。'
            '可以自然使用宝宝称呼，但不要杜撰新名字。'
            f'当前宝宝称呼：{baby_name}\n'
            f'以下是最近一周的使用统计数据：\n{current_week_usage_text}\n'
            f'以下是前一周的使用统计数据：\n{previous_week_usage_text}\n'
            f'以下是最近一周的 Viking 画像与事件摘要：\n{current_week_viking_report}\n'
            f'以下是前一周的 Viking 画像与事件摘要：\n{previous_week_viking_report}'
        )

    async def _build_usage_report(self, *, baby: Baby, preview: UsageReportPreview) -> UsageReport:
        radar, metrics, insights = await self._build_by_llm(
            baby_id=baby.id,
            baby_name=baby.name or '宝贝',
            current_week_usage=self._section_to_llm_usage(preview.current_week),
            previous_week_usage=self._section_to_llm_usage(preview.previous_week),
            has_activity=self._section_has_activity(preview.current_week) or self._section_has_activity(
                preview.previous_week),
        )

        return UsageReport(
            radar=radar,
            metrics=metrics,
            activity_trend=[item.model_copy(deep=True) for item in preview.current_week.daily_activity],
            play_preferences=[item.model_copy(deep=True) for item in preview.current_week.overview.play_preferences],
            insights=insights,
        )

    async def _build_usage_preview(self, *, baby: Baby) -> UsageReportPreview:
        start_time, end_time, dates = self._resolve_report_window()
        rows = await self._query_usage_rows(
            baby_id=baby.id,
            start_time=start_time,
            end_time=end_time,
        )
        daily_counters = UsageCounter.aggregate_rows(rows, dates)
        recent_dates, previous_dates = self._split_report_dates(dates)
        recent_daily_counters = {current_date: daily_counters[current_date] for current_date in recent_dates}
        previous_daily_counters = {current_date: daily_counters[current_date] for current_date in previous_dates}

        return UsageReportPreview(
            baby_id=baby.id,
            start_time=start_time,
            end_time=end_time,
            current_week=self._build_preview_section(recent_daily_counters),
            previous_week=self._build_preview_section(previous_daily_counters),
        )

    @classmethod
    async def _get_viking_report(
            cls,
            *,
            baby_id: int,
    ) -> tuple[str, str]:
        _, _, dates = cls._resolve_report_window()
        recent_dates, previous_dates = cls._split_report_dates(dates)
        if not recent_dates or not previous_dates:
            return '', ''

        recent_start_time = datetime.combine(recent_dates[0], time.min, tzinfo=timezone.tz_info)
        recent_end_time = datetime.combine(recent_dates[-1] + timedelta(days=1), time.min, tzinfo=timezone.tz_info)
        previous_start_time = datetime.combine(previous_dates[0], time.min, tzinfo=timezone.tz_info)
        previous_end_time = datetime.combine(previous_dates[-1] + timedelta(days=1), time.min, tzinfo=timezone.tz_info)

        recent_profile_text, recent_event_text, previous_profile_text, previous_event_text = await asyncio.gather(
            viking_memory_client.query_profile_memories_text(
                user_id=str(baby_id),
                start_time=recent_start_time,
                end_time=recent_end_time,
            ),
            viking_memory_client.query_event_memories_text(
                user_id=str(baby_id),
                start_time=recent_start_time,
                end_time=recent_end_time,
            ),
            viking_memory_client.query_profile_memories_text(
                user_id=str(baby_id),
                start_time=previous_start_time,
                end_time=previous_end_time,
            ),
            viking_memory_client.query_event_memories_text(
                user_id=str(baby_id),
                start_time=previous_start_time,
                end_time=previous_end_time,
            ),
        )
        return (
            f"画像摘要：\n{recent_profile_text}\n\n事件摘要：\n{recent_event_text}",
            f"画像摘要：\n{previous_profile_text}\n\n事件摘要：\n{previous_event_text}",
        )

    @classmethod
    async def _generate_by_llm(
            cls,
            *,
            baby_name: str,
            current_week_usage: dict[str, Any],
            previous_week_usage: dict[str, Any],
            current_week_viking_report: str,
            previous_week_viking_report: str,
    ) -> str:
        prompt = cls._build_report_prompt(
            baby_name=baby_name,
            current_week_usage=current_week_usage,
            previous_week_usage=previous_week_usage,
            current_week_viking_report=current_week_viking_report,
            previous_week_viking_report=previous_week_viking_report,
        )
        return await doubao_provider.chat(
            [
                {'role': 'system', 'content': cls.REPORT_ANALYSIS_SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt},
            ],
            model_name=DEFAULT_DOUBAO_CHAT_MODEL,
            reasoning_effort='minimal',
            temperature=0.1,
        )

    @classmethod
    def _parse_llm_response(
            cls,
            content: str,
    ) -> tuple[list[ReportRadarPoint], list[ReportMetric], ReportInsights]:
        fallback_radar, fallback_metrics, fallback_insights = cls._build_default_report_sections()

        if not content:
            return fallback_radar, fallback_metrics, fallback_insights

        try:
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError('report analysis payload must be a JSON object')

            radar_data = payload.get('radar')
            metrics_data = payload.get('metrics')
            insights_data = payload.get('insights')

            radar = (
                [ReportRadarPoint.model_validate(item) for item in radar_data]
                if isinstance(radar_data, list) and radar_data
                else fallback_radar
            )
            metrics = (
                [ReportMetric.model_validate(item) for item in metrics_data]
                if isinstance(metrics_data, list) and metrics_data
                else fallback_metrics
            )
            insights = (
                ReportInsights.model_validate(insights_data)
                if isinstance(insights_data, dict)
                else fallback_insights
            )
            return radar, metrics, insights
        except Exception as exc:
            log.warning('failed to parse LLM report analysis, error={}', exc)
            return fallback_radar, fallback_metrics, fallback_insights

    @classmethod
    async def _build_by_llm(
            cls,
            *,
            baby_id: int,
            baby_name: str,
            current_week_usage: dict[str, Any],
            previous_week_usage: dict[str, Any],
            has_activity: bool,
    ) -> tuple[list[ReportRadarPoint], list[ReportMetric], ReportInsights]:
        try:
            current_week_viking_report, previous_week_viking_report = await cls._get_viking_report(baby_id=baby_id)
        except Exception as exc:
            log.warning('failed to query Viking report for LLM analysis, baby_id={}, error={}', baby_id, exc)
            current_week_viking_report = ''
            previous_week_viking_report = ''

        if not current_week_viking_report and not previous_week_viking_report and not has_activity:
            return cls._build_default_report_sections()

        try:
            llm_content = await cls._generate_by_llm(
                baby_name=baby_name,
                current_week_usage=current_week_usage,
                previous_week_usage=previous_week_usage,
                current_week_viking_report=current_week_viking_report,
                previous_week_viking_report=previous_week_viking_report,
            )
            return cls._parse_llm_response(llm_content)
        except Exception as exc:
            log.warning('failed to generate LLM report analysis, baby_id={}, error={}', baby_id, exc)
            return cls._build_default_report_sections()

    @classmethod
    def _split_report_dates(cls, dates: list[date]) -> tuple[list[date], list[date]]:
        previous_dates = dates[:cls.REPORT_COMPARE_DAYS]
        recent_dates = dates[cls.REPORT_COMPARE_DAYS:]
        return recent_dates, previous_dates

    @staticmethod
    def _sum_daily_counters(daily_counters: dict[date, UsageCounter]) -> UsageCounter:
        counter = UsageCounter()
        for item in daily_counters.values():
            counter.chat_count += item.chat_count
            counter.active_count += item.active_count
            counter.player_count += item.player_count
            for label, count in item.play_preferences.items():
                counter.play_preferences[label] = counter.play_preferences.get(label, 0) + count
        return counter

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
            log.warning('failed to query TSDB usage rows, baby_id={}, error={}', baby_id, exc)
            return []

    async def _get_or_build_usage_preview(self, *, baby: Baby) -> UsageReportPreview:
        cache_key = self._usage_preview_cache_key(baby.id)
        cached_preview = await self._get_cached_model(
            key=cache_key,
            baby_id=baby.id,
            label='usage preview',
            model_cls=UsageReportPreview,
        )
        if cached_preview is not None:
            return cached_preview

        async with self._usage_preview_lock:
            cached_preview = await self._get_cached_model(
                key=cache_key,
                baby_id=baby.id,
                label='usage preview',
                model_cls=UsageReportPreview,
            )
            if cached_preview is not None:
                return cached_preview

            preview = await self._build_usage_preview(baby=baby)
            return await self._set_cached_model(
                key=cache_key,
                baby_id=baby.id,
                label='usage preview',
                value=preview,
            )

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
            label='usage report',
            model_cls=UsageReport,
        )
        if cached_report is not None:
            return cached_report

        async with self._usage_report_lock:
            cached_report = await self._get_cached_model(
                key=cache_key,
                baby_id=baby_id,
                label='usage report',
                model_cls=UsageReport,
            )
            if cached_report is not None:
                return cached_report

            preview = await self._get_or_build_usage_preview(baby=baby)
            report = await self._build_usage_report(baby=baby, preview=preview)
            return await self._set_cached_model(
                key=cache_key,
                baby_id=baby_id,
                label='usage report',
                value=report,
            )

    async def get_usage_preview(
            self,
            *,
            db: AsyncSession,
            user_id: int,
            baby_id: int,
    ) -> UsageReportPreview:
        baby = await baby_service.get(db=db, user_id=user_id, pk=baby_id)
        if baby is None:
            raise errors.NotFoundError(msg='宝宝不存在')

        return await self._get_or_build_usage_preview(baby=baby)


report_service: ReportService = ReportService()
