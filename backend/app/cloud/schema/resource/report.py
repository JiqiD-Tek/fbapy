# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : report.py
@Author  : OpenAI
@Date    : 2026/04/27
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from backend.common.schema import SchemaBase


class ReportRadarPoint(SchemaBase):
    label: str = Field(description='Radar dimension label')
    value: int = Field(0, description='Radar dimension value')


class ReportMetric(SchemaBase):
    label: str = Field(description='Metric label')
    value: int = Field(0, description='Metric value')
    trend: Literal['up', 'down', 'flat'] | None = Field(None, description='Metric trend')


class ReportInsight(SchemaBase):
    observations: list[str] = Field(default_factory=list, description='Observation list')
    suggestion: str = Field('', description='Next-step suggestion')


class ReportInsights(SchemaBase):
    summary: ReportInsight = Field(default_factory=ReportInsight, description='Overall insight')
    interaction: ReportInsight = Field(default_factory=ReportInsight, description='AI interaction insight')
    playback: ReportInsight = Field(default_factory=ReportInsight, description='Playback insight')


class ActivityTrendPoint(SchemaBase):
    date: str = Field(description='Date in YYYY-MM-DD format')
    chat_count: int = Field(0, description='Daily AI interaction count')
    active_count: int = Field(0, description='Daily heartbeat count')
    player_count: int = Field(0, description='Daily player event count')


class PlayPreferenceStat(SchemaBase):
    label: str = Field(description='Play preference label')
    count: int = Field(0, description='Play preference count')


class UsagePreviewOverview(SchemaBase):
    chat_count: int = Field(0, description='AI interaction count')
    active_count: int = Field(0, description='Heartbeat count')
    player_count: int = Field(0, description='Player event count')
    play_preferences: list[PlayPreferenceStat] = Field(default_factory=list, description='Play preference summary')


class UsagePreviewSection(SchemaBase):
    overview: UsagePreviewOverview = Field(default_factory=UsagePreviewOverview, description='Section overview')
    daily_activity: list[ActivityTrendPoint] = Field(default_factory=list, description='Daily activity trend')


class UsageReportPreview(SchemaBase):
    baby_id: int = Field(description='Baby id')
    start_time: datetime = Field(description='Report window start time')
    end_time: datetime = Field(description='Report window end time')
    current_week: UsagePreviewSection = Field(default_factory=UsagePreviewSection, description='Current week preview')
    previous_week: UsagePreviewSection = Field(default_factory=UsagePreviewSection, description='Previous week preview')


class UsageReport(SchemaBase):
    radar: list[ReportRadarPoint] = Field(default_factory=list, description='Radar data')
    metrics: list[ReportMetric] = Field(default_factory=list, description='Metric list')
    activity_trend: list[ActivityTrendPoint] = Field(default_factory=list, description='Activity trend')
    play_preferences: list[PlayPreferenceStat] = Field(default_factory=list, description='Play preference summary')
    insights: ReportInsights = Field(default_factory=ReportInsights, description='Insight groups')
