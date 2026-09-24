# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : report.py
@Author  : OpenAI
@Date    : 2026/04/27
"""

from __future__ import annotations

from pydantic import Field

from backend.common.schema import SchemaBase


class ReportRadarDimension(SchemaBase):
    label: str = Field(description='雷达维度名称')
    value: int = Field(0, description='雷达维度数值')


class ReportFeedbackSection(SchemaBase):
    notes: list[str] = Field(default_factory=list, description='观察记录列表')
    advice: list[str] = Field(default_factory=list, description='建议列表')


class ReportFeedback(SchemaBase):
    overview: ReportFeedbackSection = Field(default_factory=ReportFeedbackSection, description='综合反馈')
    interaction: ReportFeedbackSection = Field(default_factory=ReportFeedbackSection, description='AI 互动反馈')
    playback: ReportFeedbackSection = Field(default_factory=ReportFeedbackSection, description='播放行为反馈')


class ReportTrendPoint(SchemaBase):
    date: str = Field(description='日期，格式为 YYYY-MM-DD')
    chat_count: int = Field(0, description='每日 AI 互动次数')
    duration: int = Field(0, description='每日使用时长，单位为秒')
    play_count: int = Field(0, description='每日播放次数')
    create_count: int = Field(0, description='每日 AI 剧本创作数量')


class PlaybackStat(SchemaBase):
    label: str = Field(description='播放偏好名称')
    count: int = Field(0, description='播放次数')


class UsageReport(SchemaBase):
    current_week_radar: list[ReportRadarDimension] = Field(
        default_factory=list,
        description='最近 7 天雷达图数据',
    )
    previous_week_radar: list[ReportRadarDimension] = Field(
        default_factory=list,
        description='前 7 天雷达图数据',
    )
    current_week_trend: list[ReportTrendPoint] = Field(default_factory=list, description='最近 7 天趋势数据')
    previous_week_trend: list[ReportTrendPoint] = Field(default_factory=list, description='前 7 天趋势数据')
    playback_stats: list[PlaybackStat] = Field(default_factory=list, description='播放偏好汇总')
    feedback: ReportFeedback = Field(default_factory=ReportFeedback, description='报告反馈')
