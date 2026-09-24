from types import SimpleNamespace

from backend.app.cloud.telemetry.event_store import EventStore
from backend.app.cloud.telemetry.model.js61_event import JS61EventTable


def test_js61_event_does_not_define_toy_ids_column() -> None:
    column_names = {field.name for field in JS61EventTable.__table__.columns}

    assert 'toy_ids' not in column_names


def test_build_insert_values_does_not_store_toy_ids() -> None:
    values = EventStore._build_insert_values(
        message_ctx=SimpleNamespace(timestamp=1.5, topic='device/js61/event'),
        route=SimpleNamespace(did='did-1', category='event'),
        payload={'service': 'stage', 'payload': {'toy_ids': [10, 101]}},
        event_id='event-1',
    )

    assert values['event_id'] == 'event-1'
    assert 'toy_ids' not in values


def test_build_query_filters_do_not_use_toy_ids() -> None:
    filters = EventStore._build_query_filters(
        baby_id=1,
        start_time=None,
        end_time=None,
        category=None,
        service=None,
    )

    assert all('toy_ids' not in item for item in filters)
