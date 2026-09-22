from types import SimpleNamespace

from backend.app.cloud.telemetry.event_store import EventStore


def test_resolve_toy_ids_deduplicates_sorts_and_limits() -> None:
    assert EventStore._resolve_toy_ids({'toy_ids': [101, 10, 101, None]}) == ['10', '101']
    assert EventStore._resolve_toy_ids({'toy_ids': [1, 2, 3, 4, 5, 6]}) == ['1', '2', '3', '4', '5', '6']
    assert EventStore._resolve_toy_ids({}) == []


def test_build_toy_ids_index_uses_boundaries() -> None:
    assert EventStore._build_toy_ids_index(['10', '101']) == ',10,101,'
    assert EventStore._build_toy_ids_index([]) == ''


def test_build_insert_values_stores_one_event_toy_set() -> None:
    values = EventStore._build_insert_values(
        message_ctx=SimpleNamespace(timestamp=1.5, topic='device/js61/event'),
        route=SimpleNamespace(did='did-1', category='event'),
        payload={'service': 'stage'},
        event_id='event-1',
        toy_ids=['10', '101'],
    )

    assert values['event_id'] == 'event-1'
    assert values['toy_ids'] == ',10,101,'


def test_build_query_filters_match_exact_toy_id() -> None:
    filters = EventStore._build_query_filters(
        baby_id=1,
        start_time=None,
        end_time=None,
        category=None,
        service=None,
        toy_id='101',
    )

    assert '`toy_ids` LIKE \'%,101,%\'' in filters
