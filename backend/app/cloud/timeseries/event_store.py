from __future__ import annotations

import asyncio
import json
import uuid

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

import cachebox

from backend.app.cloud.service.baby_service import baby_service
from backend.app.cloud.timeseries.js61_event import JS61EventTable
from backend.common.log import log
from backend.database.db import async_db_session
from backend.database.tsdb import TSDBTable, quote_identifier, quote_value, tsdb_client
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from backend.common.mqtt_broker import MQTTMessageContext


@dataclass(frozen=True, slots=True)
class EventRoute:
    """Parsed routing metadata from an MQTT device event topic."""

    model: str
    did: str
    direction: str
    category: str


class EventStore:
    """Persist and query MQTT device events in TSDB."""

    TABLES_BY_MODEL: ClassVar[dict[str, TSDBTable]] = {
        'js61': JS61EventTable.__table__,
    }
    BABY_ID_CACHE: ClassVar[cachebox.TTLCache] = cachebox.TTLCache(maxsize=10000, ttl=600)
    BABY_ID_CACHE_LOCK: ClassVar[asyncio.Lock] = asyncio.Lock()

    MAX_PAYLOAD_LENGTH = 4096
    MAX_QUERY_LIMIT = 50000

    @classmethod
    def _normalize_text(cls, value: str | None, *, lowercase: bool = False) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        if not normalized:
            return None

        return normalized.lower() if lowercase else normalized

    @classmethod
    def cache_key(cls, did: str) -> str:
        return f'timeseries:baby-id:{did}'

    @classmethod
    def invalidate_baby_id_cache(cls, did: str | None) -> None:
        normalized_did = cls._normalize_text(did)
        if normalized_did is None:
            return

        cls.BABY_ID_CACHE.pop(cls.cache_key(normalized_did), None)

    @classmethod
    async def _query_baby_id(cls, did: str) -> int | None:
        async with async_db_session() as db:
            baby = await baby_service.get_by_device_did(db=db, did=did)
            return baby.id if baby is not None else None

    @classmethod
    async def _resolve_baby_id(cls, did: str) -> int | str:
        cache_key = cls.cache_key(did)
        if cache_key in cls.BABY_ID_CACHE:
            return cls.BABY_ID_CACHE[cache_key]

        async with cls.BABY_ID_CACHE_LOCK:
            if cache_key in cls.BABY_ID_CACHE:
                return cls.BABY_ID_CACHE[cache_key]

            baby_id = await cls._query_baby_id(did)
            cls.BABY_ID_CACHE[cache_key] = baby_id
            return baby_id

    @classmethod
    async def _resolve_subtable_name(cls, model: str, baby_id: int) -> str:
        return f'{model}_{baby_id}'

    @classmethod
    def _ensure_tsdb_ready(cls, *, action: str) -> bool:
        if not tsdb_client.enabled:
            log.debug(f'skip TSDB {action} because TSDB client is not enabled')
            return False

        return True

    @classmethod
    def _resolve_model_table(cls, model: str) -> tuple[str, TSDBTable] | None:
        model_key = cls._normalize_text(model, lowercase=True)
        if model_key is None:
            return None

        table = cls.TABLES_BY_MODEL.get(model_key)
        if table is None:
            return None

        return model_key, table

    @classmethod
    def _parse_message_topic(cls, topic: str) -> EventRoute | None:
        parts = [segment.strip() for segment in topic.split('/') if segment.strip()]
        if len(parts) < 4:
            return None

        return EventRoute(
            model=parts[0].lower(),
            did=parts[1],
            direction=parts[2],
            category=parts[3],
        )

    @classmethod
    def _serialize_message_payload(cls, topic: str, payload: object) -> str:
        text = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))

        if len(text) > cls.MAX_PAYLOAD_LENGTH:
            log.debug(f'payload is too long, topic={topic}, payload={text}')
            return text[: cls.MAX_PAYLOAD_LENGTH - 3] + '...'

        return text

    @classmethod
    def _normalize_time_filter(cls, value: datetime | str | None) -> datetime | None:
        if value is None:
            return None

        if isinstance(value, str):
            return timezone.from_str(value)

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.tz_info)

        return timezone.from_datetime(value)

    @classmethod
    def _resolve_time_range(
            cls,
            *,
            start_time: datetime | str | None,
            end_time: datetime | str | None,
    ) -> tuple[datetime | None, datetime | None]:
        normalized_start = cls._normalize_time_filter(start_time)
        normalized_end = cls._normalize_time_filter(end_time)

        if normalized_start is None and normalized_end is None:
            normalized_start = timezone.now() - timedelta(days=30)

        if normalized_start is not None and normalized_end is not None and normalized_start > normalized_end:
            raise ValueError('start_time must be earlier than or equal to end_time')

        return normalized_start, normalized_end

    @classmethod
    def _build_query_filters(
            cls,
            *,
            start_time: datetime | None,
            end_time: datetime | None,
            direction: str | None,
            category: str | None,
            service: str | None,
    ) -> list[str]:
        filters: list[str] = []

        if start_time is not None:
            filters.append(f'ts >= {int(start_time.timestamp() * 1000)}')
        if end_time is not None:
            filters.append(f'ts <= {int(end_time.timestamp() * 1000)}')

        for field_name, field_value in (
                ('direction', direction),
                ('category', category),
                ('service', service),
        ):
            normalized_value = cls._normalize_text(field_value)
            if normalized_value is None:
                continue
            filters.append(f'{quote_identifier(field_name)} = {quote_value(normalized_value)}')

        return filters

    @classmethod
    def _build_insert_tags(cls, *, baby_id: int) -> dict[str, int]:
        return {
            'baby_id': baby_id,
        }

    @classmethod
    def _build_insert_values(cls, message_ctx: MQTTMessageContext, route: EventRoute) -> dict[str, object]:
        return {
            'ts': int(message_ctx.timestamp * 1000),
            'event_id': uuid.uuid4().hex,
            'did': route.did,
            'direction': route.direction,
            'category': route.category,
            'service': 'mqtt',  # TODO: get from message
            'topic': message_ctx.topic,
            'payload': cls._serialize_message_payload(message_ctx.topic, message_ctx.payload),
        }

    @classmethod
    def _get_selected_columns(cls, table: TSDBTable) -> tuple[tuple[str, ...], str]:
        column_names = tuple(field.name for field in table.columns)
        selected_columns = ', '.join(quote_identifier(name) for name in column_names)
        return column_names, selected_columns

    @classmethod
    def _build_query_sql(
            cls,
            *,
            subtable_name: str,
            selected_columns: str,
            filters: list[str],
            limit: int,
    ) -> str:
        where_sql = f" WHERE {' AND '.join(filters)}" if filters else ''
        return (
            f'SELECT {selected_columns} FROM {quote_identifier(subtable_name)}'
            f'{where_sql} '
            f'ORDER BY ts DESC LIMIT {limit}'
        )

    @classmethod
    def _map_query_rows(
            cls,
            *,
            column_names: tuple[str, ...],
            rows: list[tuple[object, ...]] | list[list[object]],
    ) -> list[dict[str, object]]:
        return [dict(zip(column_names, row, strict=False)) for row in rows]

    @classmethod
    async def insert(cls, message_ctx: MQTTMessageContext) -> None:
        """Persist one MQTT message into the matching TSDB subtable."""

        if not cls._ensure_tsdb_ready(action='message insert'):
            log.debug('TSDB is not ready, skipping message insert')
            return

        route = cls._parse_message_topic(message_ctx.topic)
        if route is None:
            log.debug(f'invalid message topic, topic={message_ctx.topic}')
            return

        resolved_table = cls._resolve_model_table(route.model)
        if resolved_table is None:
            log.debug(f'model not found for model={route.model}')
            return

        baby_id = await cls._resolve_baby_id(route.did)
        if baby_id is None:
            log.debug(f'baby_id not found for did={route.did}')
            return

        model_key, table = resolved_table
        try:
            await table.insert(
                tsdb_client,
                subtable_name=await cls._resolve_subtable_name(model_key, baby_id),
                tags=cls._build_insert_tags(baby_id=baby_id),
                values=cls._build_insert_values(message_ctx, route),
            )
        except Exception as exc:
            log.error(
                f'failed to ingest MQTT message into TSDB, table={table.name}, topic={message_ctx.topic}, error={exc}'
            )

    @classmethod
    async def query(
            cls,
            *,
            model: str,
            baby_id: int,
            start_time: datetime | str | None = None,
            end_time: datetime | str | None = None,
            direction: str | None = None,
            category: str | None = None,
            service: str | None = None,
            limit: int = 10000,
    ) -> list[dict[str, object]]:
        """Query device event messages from one TSDB subtable."""

        resolved_table = cls._resolve_model_table(model)
        if resolved_table is None:
            return []

        if not cls._ensure_tsdb_ready(action='message query'):
            return []

        model_key, table = resolved_table
        range_start, range_end = cls._resolve_time_range(start_time=start_time, end_time=end_time)
        safe_limit = max(1, min(limit, cls.MAX_QUERY_LIMIT))
        column_names, selected_columns = cls._get_selected_columns(table)
        filters = cls._build_query_filters(
            start_time=range_start,
            end_time=range_end,
            direction=direction,
            category=category,
            service=service,
        )

        sql = cls._build_query_sql(
            subtable_name=await cls._resolve_subtable_name(model_key, baby_id),
            selected_columns=selected_columns,
            filters=filters,
            limit=safe_limit,
        )
        result = await tsdb_client.query(sql)
        rows = result.get('data', [])

        return cls._map_query_rows(column_names=column_names, rows=rows)


event_store = EventStore()


async def main() -> None:
    await tsdb_client.init()
    ret = await event_store.query(
        model='js61',
        baby_id=1,
        start_time='2026-04-01 00:00:00',
        end_time='2026-05-01 00:00:00',
        limit=10000,
    )
    print(ret)


if __name__ == '__main__':
    asyncio.run(main())
