import asyncio

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from backend.app.cloud.service.resource.report_service import ReportService, report_service


def test_build_usage_preview_uses_device_chat_counts(monkeypatch):
    start_time = datetime(2026, 8, 11, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)
    dates = [start_time.date() + timedelta(days=offset) for offset in range(14)]
    target_day = date(2026, 8, 20)

    async def fake_query_usage_rows(cls, *, baby_id, start_time, end_time):  # noqa: ARG001
        return [
            {'ts': datetime(2026, 8, 20, 8, 0, tzinfo=timezone.utc), 'service': 'chat'},
            {'ts': datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc), 'service': 'active'},
            {'ts': datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc), 'service': 'play'},
        ]

    async def fake_query_device_chat_counts(*, db, baby_id, start_time, end_time):  # noqa: ARG001
        return {target_day: 3}

    monkeypatch.setattr(
        ReportService,
        '_resolve_report_window',
        classmethod(lambda cls: (start_time, end_time, dates)),
    )
    monkeypatch.setattr(
        ReportService,
        '_query_usage_rows',
        classmethod(fake_query_usage_rows),
    )
    monkeypatch.setattr(
        ReportService,
        '_query_device_chat_counts',
        staticmethod(fake_query_device_chat_counts),
    )

    preview = asyncio.run(report_service._build_usage_preview(db=object(), baby=SimpleNamespace(id=7)))

    current_day = next(item for item in preview.current_week.daily_activity if item.date == target_day.isoformat())
    assert current_day.chat_count == 3
    assert current_day.duration == 300
    assert current_day.play_count == 1
    assert preview.current_week.overview.chat_count == 3
