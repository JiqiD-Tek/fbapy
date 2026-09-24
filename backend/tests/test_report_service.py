import asyncio

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from backend.app.cloud.service.resource.report_service import (
    ReportService,
    device_chat_dao,
    script_dao,
)


def test_query_window_data_builds_usage_stats(monkeypatch):
    start_time = datetime(2026, 8, 18, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)
    target_day = date(2026, 8, 20)

    async def fake_query_usage_rows(cls, *, baby_id, start_time, end_time):  # noqa: ARG001
        return [
            {'ts': datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc), 'service': 'active'},
            {
                'ts': datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
                'service': 'play',
                'payload': {'content_type': 2},
            },
        ]

    async def fake_query_chat_records(cls, *, db, baby_id, start_time, end_time):  # noqa: ARG001
        created_time = datetime(2026, 8, 20, 8, 0, tzinfo=timezone.utc)
        return [(created_time, '问题一', [2, 2, 1]), (created_time, '问题二', [])]

    async def fake_query_generated_scripts(cls, *, db, baby_id, start_time, end_time):  # noqa: ARG001
        created_time = datetime(2026, 8, 20, 11, 0, tzinfo=timezone.utc)
        return [(created_time, '恐龙故事'), (created_time, '太空故事')]

    monkeypatch.setattr(ReportService, '_query_usage_rows', classmethod(fake_query_usage_rows))
    monkeypatch.setattr(ReportService, '_query_chat_records', classmethod(fake_query_chat_records))
    monkeypatch.setattr(ReportService, '_query_generated_scripts', classmethod(fake_query_generated_scripts))

    result = asyncio.run(
        ReportService._query_window_data(
            db=object(), baby_id=7, start_time=start_time, end_time=end_time,
        )
    )
    stats = result['daily_stats'][target_day]
    trend = ReportService._build_trend(result['daily_stats'])
    target_trend = next(item for item in trend if item.date == target_day.isoformat())
    play_prefs = ReportService._build_play_prefs(result['daily_stats'])

    assert len(result['daily_stats']) == 7
    assert stats['chat_count'] == 2
    assert stats['toy_counts'] == {2: 2, 1: 1}
    assert target_trend.duration == 300
    assert target_trend.play_count == 1
    assert target_trend.create_count == 2
    assert [(item.label, item.count) for item in play_prefs] == [('科学', 1)]


def test_build_usage_report_returns_current_and_previous_week_trends(monkeypatch) -> None:
    start_time = datetime(2026, 8, 11, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)

    async def fake_query_window_data(cls, *, db, baby_id, start_time, end_time):  # noqa: ARG001
        daily_stats = {
            start_time.date() + timedelta(days=offset): ReportService._new_daily_usage()
            for offset in range((end_time.date() - start_time.date()).days)
        }
        return {
            'daily_stats': daily_stats,
            'user_messages': [],
            'toy_counts': {},
            'story_topics': [],
        }

    monkeypatch.setattr(
        ReportService,
        '_resolve_report_window',
        classmethod(lambda cls: (start_time, end_time)),
    )
    monkeypatch.setattr(ReportService, '_query_window_data', classmethod(fake_query_window_data))

    report = asyncio.run(
        ReportService()._build_usage_report(
            db=object(),
            baby=SimpleNamespace(id=7, name='小雨'),
        )
    )

    assert len(report.current_week_trend) == 7
    assert len(report.previous_week_trend) == 7
    assert report.current_week_trend[0].date == '2026-08-18'
    assert report.previous_week_trend[0].date == '2026-08-11'


def test_query_chat_records_reads_chat_and_reply_toy_ids(monkeypatch) -> None:
    target_day = datetime(2026, 8, 20, 8, 0, tzinfo=timezone.utc)
    records = [
        (target_day, {'user_message': '问题一', 'replies': [{'toy_id': 2}, {'toy_id': '2'}, {'toy_id': 1}]}),
        (target_day, {'user_message': '问题二', 'replies': [{'toy_id': None}, {'toy_id': True}, {'toy_id': 0}]}),
    ]

    async def fake_get_contents_by_time_range(db, *, baby_id, start_time, end_time, limit):  # noqa: ARG001
        return records

    monkeypatch.setattr(device_chat_dao, 'get_contents_by_time_range', fake_get_contents_by_time_range)
    result = asyncio.run(
        ReportService._query_chat_records(
            db=object(),
            baby_id=7,
            start_time=target_day - timedelta(days=1),
            end_time=target_day + timedelta(days=1),
        )
    )

    assert result == [
        (target_day, '问题一', [2, 2, 1]),
        (target_day, '问题二', []),
    ]


def test_report_sources_only_keep_user_message_story_topic_and_time(monkeypatch) -> None:
    target_time = datetime(2026, 8, 20, 8, 30, 45, tzinfo=timezone.utc)

    async def fake_get_contents(db, *, baby_id, start_time, end_time, limit):  # noqa: ARG001
        return [(target_time, {'user_message': '我想去太空', 'replies': [{'reply_message': 'AI 回复'}]})]

    async def fake_get_topics(db, *, baby_id, start_time, end_time, limit):  # noqa: ARG001
        return [(target_time, '创作一个月球探险故事')]

    monkeypatch.setattr(device_chat_dao, 'get_contents_by_time_range', fake_get_contents)
    monkeypatch.setattr(script_dao, 'get_generated_topics_by_time_range', fake_get_topics)

    chat_records = asyncio.run(
        ReportService._query_chat_records(
            db=object(), baby_id=7, start_time=target_time - timedelta(days=1), end_time=target_time,
        )
    )
    selected_messages = ReportService._format_user_messages(chat_records)
    generated_scripts = asyncio.run(
        ReportService._query_generated_scripts(
            db=object(), baby_id=7, start_time=target_time - timedelta(days=1), end_time=target_time,
        )
    )
    story_topics = ReportService._format_story_topics(generated_scripts)

    assert selected_messages == [{'time': '2026-08-20T08:30:45+00:00', 'content': '我想去太空'}]
    assert story_topics == [{'time': '2026-08-20T08:30:45+00:00', 'topic': '创作一个月球探险故事'}]


def test_build_report_prompt_uses_chats_and_generated_stories_without_viking() -> None:
    prompt = ReportService._build_report_prompt(
        baby_name='小雨',
        current_week_usage={'overview': {'chat_count': 1, 'play_count': 2}},
        previous_week_usage={'overview': {'chat_count': 0, 'play_count': 1}},
        current_week_user_messages=[{'time': '2026-08-20T08:00:00', 'content': '今天想听恐龙故事'}],
        previous_week_user_messages=[],
        current_week_story_topics=[{'time': '2026-08-21T09:00:00', 'topic': '勇敢的小恐龙'}],
        previous_week_story_topics=[],
    )

    assert '今天想听恐龙故事' in prompt
    assert '勇敢的小恐龙' in prompt
    assert '2026-08-20T08:00:00' in prompt
    assert 'device_chat.content.user_message' in prompt
    assert 'script.remark' in prompt
    assert 'Viking' not in prompt
    assert 'current_week_radar' in prompt
    assert 'previous_week_radar' in prompt
    assert 'feedback' in prompt
    assert '【本周数据】' in prompt
    assert '【上周数据】' in prompt
    assert '本周暂无相关记录' in prompt
    assert '上周暂无相关记录' in prompt
    assert '"metrics"' not in prompt
    assert 'insights' not in prompt


def test_parse_llm_response_returns_two_week_radar_data() -> None:
    content = '''{
        "current_week_radar": [
            {"label": "表达", "value": 60},
            {"label": "情感", "value": 50},
            {"label": "专注", "value": 40},
            {"label": "想象", "value": 70},
            {"label": "逻辑", "value": 30}
        ],
        "previous_week_radar": [
            {"label": "表达", "value": 50},
            {"label": "情感", "value": 45},
            {"label": "专注", "value": 35},
            {"label": "想象", "value": 55},
            {"label": "逻辑", "value": 30}
        ],
        "feedback": {
            "overview": {"notes": ["整体互动有所增加。"], "advice": ["继续保持互动。"]},
            "interaction": {"notes": [], "advice": []},
            "playback": {"notes": [], "advice": []}
        }
    }'''

    current_week_radar, previous_week_radar, feedback = ReportService._parse_llm_response(content)

    assert [item.value for item in current_week_radar] == [60, 50, 40, 70, 30]
    assert [item.value for item in previous_week_radar] == [50, 45, 35, 55, 30]
    assert feedback.overview.notes == ['整体互动有所增加。']
    assert feedback.overview.advice == ['继续保持互动。']


def test_default_report_sections_returns_independent_radar_lists() -> None:
    current_week_radar, previous_week_radar, _ = ReportService._build_default_report_sections()

    current_week_radar[0].value = 80

    assert previous_week_radar[0].value == 0
