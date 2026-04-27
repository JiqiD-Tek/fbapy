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
from typing import Any, ClassVar

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
)
from backend.app.cloud.service.baby_service import baby_service
from backend.app.cloud.timeseries.event_store import event_store
from backend.common.exception import errors
from backend.common.log import log
from backend.common.providers.doubao import DEFAULT_DOUBAO_CHAT_MODEL, doubao_provider
from backend.common.providers.viking_memory import viking_memory_client
from backend.utils.timezone import timezone


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

    def has_activity(self) -> bool:
        return (self.chat_count + self.active_count + self.player_count) > 0

    def to_trend_point(self, current_date: date) -> ActivityTrendPoint:
        return ActivityTrendPoint(
            date=current_date.isoformat(),
            chat_count=self.chat_count,
            active_count=self.active_count,
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
    ) -> tuple[UsageCounter, dict[date, UsageCounter]]:
        overall_counter = cls()
        daily_counters = {current_date: cls() for current_date in dates}

        for row in rows:
            event_date, service, play_preference = cls._resolve_row(row)
            if event_date is None or event_date not in daily_counters:
                continue

            overall_counter.add(service, play_preference=play_preference)
            daily_counters[event_date].add(service, play_preference=play_preference)

        return overall_counter, daily_counters


@dataclass(slots=True)
class ReportCacheEntry:
    expires_at: datetime
    report: UsageReport


class ReportService:
    REPORT_DAYS: ClassVar[int] = 7
    REPORT_QUERY_LIMIT: ClassVar[int] = 20000
    REPORT_ANALYSIS_SYSTEM_PROMPT: ClassVar[str] = (
        '你擅长生成结构化、克制、可直接解析的儿童成长分析结果。'
    )
    REPORT_ANALYSIS_PROMPT_TEMPLATE: ClassVar[str] = (
        '你是儿童成长报告分析助手。'
        '请基于使用统计数据和用户画像摘要，输出一个 JSON 对象，不要输出 Markdown，不要输出解释。'
        'JSON 结构必须为：'
        '{'
        '"radar":[{"label":"词汇","value":0},{"label":"情感","value":0},{"label":"专注力","value":0},{"label":"想象力","value":0},{"label":"逻辑","value":0}],'
        '"metrics":[{"label":"口语词汇","value":0,"trend":"flat"},{"label":"情感表达","value":0,"trend":"flat"},{"label":"专注力","value":0,"trend":"flat"},{"label":"想象力","value":0,"trend":"flat"},{"label":"逻辑理解","value":0,"trend":"flat"}],'
        '"insights":{"summary":{"observations":[],"suggestion":""},"interaction":{"observations":[],"suggestion":""},"playback":{"observations":[],"suggestion":""}}'
        '}'
        '要求：'
        '1. value 取值范围 0 到 100。'
        '2. trend 只能是 up、down、flat。'
        '3. observations 为简短中文句子数组。'
        '4. 如果信息不足，请给出保守判断，不要编造细节。'
        '5. 优先结合使用统计与画像摘要一起判断。'
        '6. summary / interaction / playback 三个模块的文案风格，请参考儿童成长周报卡片。'
        '7. summary.observations 聚焦整体成长观察，写 1 到 2 条，每条一句话，语气温和、具体，适合家长阅读。'
        '8. interaction.observations 聚焦 AI 互动趋势、提问表达、互动活跃度，写 1 到 2 条。'
        '9. playback.observations 聚焦收听习惯、内容偏好、播放活跃度，写 1 到 2 条。'
        '10. suggestion 为单句建议，风格参考“下周建议”，要自然、可执行、面向家长。'
        '11. 如果适合，可以自然使用宝宝称呼；优先使用提供的名字，不要杜撰新名字。'
        '12. 不要把统计数字生硬罗列成报表，要组织成自然语言，但若关键数字确实有帮助，可以少量引用。'
        '当前宝宝称呼：{baby_name}\n'
        '以下是使用统计数据：\n{usage_summary}\n'
        '以下是 Viking 画像与事件摘要：\n{viking_report}'
    )

    _usage_cache: ClassVar[dict[int, ReportCacheEntry]] = {}
    _usage_cache_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    def _resolve_report_window(cls) -> tuple[datetime, datetime, list[date]]:
        end_time = timezone.now()
        start_date = (end_time - timedelta(days=cls.REPORT_DAYS - 1)).date()
        start_time = datetime.combine(start_date, time.min, tzinfo=timezone.tz_info)
        dates = [start_date + timedelta(days=offset) for offset in range(cls.REPORT_DAYS)]
        return start_time, end_time, dates

    @staticmethod
    def _build_report_insights() -> ReportInsights:
        return ReportInsights(
            summary=ReportInsight(
                observations=[
                    '本周成长数据已完成汇总，正在结合互动与收听情况生成更细致的成长观察。',
                ],
                suggestion='下周建议：继续保持规律陪伴，帮助宝宝在自然互动中积累更多表达和探索体验。',
            ),
            interaction=ReportInsight(
                observations=[
                    'AI互动数据已纳入统计，后续会结合提问内容和互动频率补充更具体的交流趋势。',
                ],
                suggestion='下周建议：可以多引导宝宝开口提问和表达想法，帮助观察互动兴趣的变化。',
            ),
            playback=ReportInsight(
                observations=[
                    '收听与播放数据已完成整理，后续会结合内容偏好生成更具体的使用习惯小结。',
                ],
                suggestion='下周建议：可以搭配不同主题内容轮换收听，继续观察宝宝对故事和互动内容的偏好。',
            ),
        )

    @staticmethod
    def _build_report_radar() -> list[ReportRadarPoint]:
        return [
            ReportRadarPoint(label='词汇', value=100),
            ReportRadarPoint(label='情感', value=100),
            ReportRadarPoint(label='专注力', value=100),
            ReportRadarPoint(label='想象力', value=100),
            ReportRadarPoint(label='逻辑', value=100),
        ]

    @staticmethod
    def _build_report_metrics() -> list[ReportMetric]:
        return [
            ReportMetric(label='口语词汇', value=100, trend='flat'),
            ReportMetric(label='情感表达', value=100, trend='flat'),
            ReportMetric(label='专注力', value=100, trend='flat'),
            ReportMetric(label='想象力', value=100, trend='flat'),
            ReportMetric(label='逻辑理解', value=100, trend='flat'),
        ]

    @classmethod
    def _build_default_report_sections(
            cls,
    ) -> tuple[list[ReportRadarPoint], list[ReportMetric], ReportInsights]:
        return (
            cls._build_report_radar(),
            cls._build_report_metrics(),
            cls._build_report_insights(),
        )

    async def _build_usage_report(self, *, baby: Baby) -> UsageReport:
        start_time, end_time, dates = self._resolve_report_window()
        rows = await self._query_usage_rows(
            baby_id=baby.id,
            start_time=start_time,
            end_time=end_time,
        )

        overall_counter, daily_counters = UsageCounter.aggregate_rows(rows, dates)
        radar, metrics, insights = await self._build_by_llm(
            baby_id=baby.id,
            baby_name=baby.name or '宝宝',
            overall_counter=overall_counter,
            daily_counters=daily_counters,
        )

        return UsageReport(
            radar=radar,
            metrics=metrics,
            activity_trend=[
                counter.to_trend_point(current_date)
                for current_date, counter in daily_counters.items()
            ],
            play_preferences=overall_counter.to_play_preferences(),
            insights=insights,
        )

    @classmethod
    def _get_cached_usage_report(cls, baby_id: int) -> UsageReport | None:
        cached_entry = cls._usage_cache.get(baby_id)
        if cached_entry is None:
            return None

        if timezone.now() >= cached_entry.expires_at:
            cls._usage_cache.pop(baby_id, None)
            return None

        return cached_entry.report.model_copy(deep=True)

    @classmethod
    def _set_cached_usage_report(cls, baby_id: int, report: UsageReport) -> UsageReport:
        tomorrow = timezone.now().date() + timedelta(days=1)
        expires_at = datetime.combine(tomorrow, time.min, tzinfo=timezone.tz_info)
        cls._usage_cache[baby_id] = ReportCacheEntry(
            expires_at=expires_at,
            report=report.model_copy(deep=True),
        )
        return report

    @classmethod
    async def _get_viking_report(
            cls,
            *,
            baby_id: int,
    ) -> str:
        start_time, end_time, _ = cls._resolve_report_window()

        profile_text, event_text = await asyncio.gather(
            viking_memory_client.query_profile_memories_text(
                user_id=str(baby_id),
                start_time=start_time,
                end_time=end_time,
            ),
            viking_memory_client.query_event_memories_text(
                user_id=str(baby_id),
                start_time=start_time,
                end_time=end_time,
            ),
        )
        return f"画像摘要：\n{profile_text}\n\n事件摘要：\n{event_text}"

    @classmethod
    def _build_usage_summary_for_llm(
            cls,
            *,
            overall_counter: UsageCounter,
            daily_counters: dict[date, UsageCounter],
    ) -> dict[str, Any]:
        return {
            'report_days': cls.REPORT_DAYS,
            'overview': {
                'chat_count': overall_counter.chat_count,
                'active_count': overall_counter.active_count,
                'player_count': overall_counter.player_count,
                'play_preferences': [
                    item.model_dump()
                    for item in overall_counter.to_play_preferences()
                ],
            },
            'daily_activity': [
                counter.to_trend_point(current_date).model_dump()
                for current_date, counter in daily_counters.items()
            ],
        }

    @classmethod
    async def _generate_by_llm(
            cls,
            *,
            baby_name: str,
            usage_summary: dict[str, Any],
            viking_report: str,
    ) -> str:
        prompt = cls.REPORT_ANALYSIS_PROMPT_TEMPLATE.format(
            baby_name=baby_name,
            usage_summary=json.dumps(usage_summary, ensure_ascii=False),
            viking_report=viking_report,
        )
        return await doubao_provider.chat(
            [
                {'role': 'system', 'content': cls.REPORT_ANALYSIS_SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt},
            ],
            model_name=DEFAULT_DOUBAO_CHAT_MODEL,
            reasoning_effort='minimal',
            temperature=0.3,
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
            overall_counter: UsageCounter,
            daily_counters: dict[date, UsageCounter],
    ) -> tuple[list[ReportRadarPoint], list[ReportMetric], ReportInsights]:
        usage_summary = cls._build_usage_summary_for_llm(
            overall_counter=overall_counter,
            daily_counters=daily_counters,
        )
        try:
            viking_report = await cls._get_viking_report(baby_id=baby_id)
        except Exception as exc:
            log.warning('failed to query Viking report for LLM analysis, baby_id={}, error={}', baby_id, exc)
            viking_report = ''

        if not viking_report and not overall_counter.has_activity():
            return cls._build_default_report_sections()

        try:
            llm_content = await cls._generate_by_llm(
                baby_name=baby_name,
                usage_summary=usage_summary,
                viking_report=viking_report,
            )
            return cls._parse_llm_response(llm_content)
        except Exception as exc:
            log.warning('failed to generate LLM report analysis, baby_id={}, error={}', baby_id, exc)
            return cls._build_default_report_sections()

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
            return await event_store.query(
                model=model,
                baby_id=baby_id,
                start_time=start_time,
                end_time=end_time,
                limit=cls.REPORT_QUERY_LIMIT,
            )
        except Exception as exc:
            log.warning('failed to query TSDB usage rows, baby_id={}, error={}', baby_id, exc)
            return []

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

        cached_report = self._get_cached_usage_report(baby_id)
        if cached_report is not None:
            return cached_report

        async with self._usage_cache_lock:
            cached_report = self._get_cached_usage_report(baby_id)
            if cached_report is not None:
                return cached_report

            report = await self._build_usage_report(baby=baby)
            return self._set_cached_usage_report(baby_id, report)


report_service: ReportService = ReportService()
