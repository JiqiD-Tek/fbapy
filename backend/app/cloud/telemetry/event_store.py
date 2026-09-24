from __future__ import annotations

import asyncio
import json
import uuid

from asyncio import Queue, QueueEmpty
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

import cachebox

from backend.app.cloud.service.baby_service import baby_service
from backend.app.cloud.service.device.topic import MQTTEventRoute, parse_mqtt_topic
from backend.app.cloud.telemetry.model.js61_event import JS61EventTable
from backend.common._queue import batch_dequeue
from backend.common.log import log
from backend.common.observability.prometheus.queue import inc_queue_exception, observe_queue_size
from backend.database.db import async_db_session
from backend.database.tsdb import TSDBTable, quote_identifier, quote_value, tsdb
from backend.core.conf import settings
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from backend.common.mqtt import MQTTMessageContext


@dataclass(slots=True)
class TSDBInsertItem:
    table: TSDBTable
    subtable_name: str
    tags: dict[str, str]
    values: dict[str, object]


class EventStore:
    """将 MQTT 设备事件写入时序数据库并提供查询能力。"""

    # 设备型号与事件稳定表的映射，后续新增设备型号时在此注册。
    MODEL_TABLES: ClassVar[dict[str, TSDBTable]] = {
        'js61': JS61EventTable.__table__,
    }

    # 缓存 DID 对应的宝宝 ID，并使用 DID 级锁避免缓存未命中时重复查询数据库。
    BABY_ID_CACHE: ClassVar[cachebox.TTLCache] = cachebox.TTLCache(maxsize=10000, global_ttl=600)
    DID_LOCKS: ClassVar[dict[str, asyncio.Lock]] = {}
    # 保护 DID 锁字典，避免并发创建同一个 DID 的多把锁。
    DID_LOCKS_GUARD: ClassVar[asyncio.Lock] = asyncio.Lock()

    # MQTT 消费只负责入队，由后台写入任务合并批量写入 TSDB。
    TSDB_WRITE_QUEUE: ClassVar[Queue[TSDBInsertItem]] = Queue(maxsize=settings.TSDB_WRITE_QUEUE_MAXSIZE)
    TSDB_WRITER_TASKS: ClassVar[list[asyncio.Task]] = []
    TSDB_WRITER_STARTED: ClassVar[bool] = False
    TSDB_WRITER_LOCK: ClassVar[asyncio.Lock] = asyncio.Lock()

    # 分别对应 payload 字符数上限和单次查询返回行数上限。
    MAX_PAYLOAD_CHARS = 4096
    MAX_QUERY_ROWS = 50000

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
    async def _resolve_baby_id(cls, did: str) -> int | None:
        cache_key = cls.cache_key(did)
        if cache_key in cls.BABY_ID_CACHE:
            return cls.BABY_ID_CACHE[cache_key]

        async with await cls._get_did_lock(did):
            if cache_key in cls.BABY_ID_CACHE:
                return cls.BABY_ID_CACHE[cache_key]

            baby_id = await cls._query_baby_id(did)
            cls.BABY_ID_CACHE[cache_key] = baby_id
            return baby_id

    @classmethod
    async def _get_did_lock(cls, did: str) -> asyncio.Lock:
        async with cls.DID_LOCKS_GUARD:
            lock = cls.DID_LOCKS.get(did)
            if lock is None:
                lock = asyncio.Lock()
                cls.DID_LOCKS[did] = lock
            return lock

    @classmethod
    def _resolve_subtable_name(cls, model: str, baby_id: int) -> str:
        return f'{model}_{baby_id}'

    @classmethod
    def _ensure_tsdb_ready(cls, *, action: str, write: bool) -> bool:
        if not tsdb.enabled:
            log.debug(f'跳过时序数据库操作 {action}：时序数据库客户端未启用')
            return False

        ready = tsdb.write_ready if write else tsdb.read_ready
        if not ready:
            client_type = '写客户端' if write else '读客户端'
            log.debug(f'跳过时序数据库操作 {action}：时序数据库{client_type}未就绪')
            return False

        return True

    @classmethod
    def _ensure_tsdb_read_ready(cls, *, action: str) -> bool:
        return cls._ensure_tsdb_ready(action=action, write=False)

    @classmethod
    def _ensure_tsdb_write_ready(cls, *, action: str) -> bool:
        return cls._ensure_tsdb_ready(action=action, write=True)

    @classmethod
    def _resolve_model_table(cls, model: str) -> tuple[str, TSDBTable] | None:
        model_key = cls._normalize_text(model, lowercase=True)
        if model_key is None:
            return None

        table = cls.MODEL_TABLES.get(model_key)
        if table is None:
            return None

        return model_key, table

    @classmethod
    def _serialize_message_payload(cls, topic: str, payload: object) -> str:
        if isinstance(payload, dict):
            payload = payload.get('payload', payload)

        text = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))

        if len(text) > cls.MAX_PAYLOAD_CHARS:
            log.debug(f'事件载荷过长，将截断：topic={topic}, payload={text}')
            return text[: cls.MAX_PAYLOAD_CHARS - 3] + '...'

        return text

    @classmethod
    def _resolve_service_name(cls, payload: object) -> str:
        if isinstance(payload, dict):
            service = cls._normalize_text(payload.get('service'))
            if service is not None:
                return service

        return 'mqtt'

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
            raise ValueError('开始时间必须早于或等于结束时间')

        return normalized_start, normalized_end

    @classmethod
    def _build_query_filters(
            cls,
            *,
            baby_id: int,
            start_time: datetime | None,
            end_time: datetime | None,
            category: str | None,
            service: str | None,
    ) -> list[str]:
        filters: list[str] = [f'{quote_identifier("baby_id")} = {quote_value(str(baby_id))}']

        if start_time is not None:
            filters.append(f'ts >= {int(start_time.timestamp() * 1000)}')
        if end_time is not None:
            filters.append(f'ts <= {int(end_time.timestamp() * 1000)}')

        for field_name, field_value in (
                ('category', category),
                ('service', service),
        ):
            normalized_value = cls._normalize_text(field_value)
            if normalized_value is None:
                continue
            filters.append(f'{quote_identifier(field_name)} = {quote_value(normalized_value)}')

        return filters

    @classmethod
    def _build_insert_tags(cls, *, baby_id: int | str) -> dict[str, str]:
        return {
            'baby_id': str(baby_id),
        }

    @classmethod
    def _build_insert_values(
            cls,
            message_ctx: MQTTMessageContext,
            route: MQTTEventRoute,
            payload: object,
            event_id: str,
    ) -> dict[str, object]:
        return {
            'ts': int(message_ctx.timestamp * 1000),
            'event_id': event_id,
            'did': route.did,
            'category': route.category,
            'service': cls._resolve_service_name(payload),
            'topic': message_ctx.topic,
            'payload': cls._serialize_message_payload(message_ctx.topic, payload),
        }

    @classmethod
    async def start(cls) -> None:
        if not cls._ensure_tsdb_write_ready(action='写入器启动'):
            return

        if cls.TSDB_WRITER_STARTED:
            return

        async with cls.TSDB_WRITER_LOCK:
            if cls.TSDB_WRITER_STARTED:
                return

            cls.TSDB_WRITER_TASKS = [
                asyncio.create_task(cls._writer_worker(index), name=f'tsdb_writer_worker_{index}')
                for index in range(settings.TSDB_WRITE_WORKERS)
            ]
            cls.TSDB_WRITER_STARTED = True
            observe_queue_size(cls.TSDB_WRITE_QUEUE, queue_name='tsdb_write')
            log.info(
                f'时序数据库写入器已启动：工作线程数={settings.TSDB_WRITE_WORKERS}，'
                f'批量大小={settings.TSDB_WRITE_BATCH_SIZE}，队列容量={settings.TSDB_WRITE_QUEUE_MAXSIZE}'
            )

    @classmethod
    async def _writer_worker(cls, worker_id: int) -> None:
        while True:
            items = await batch_dequeue(
                cls.TSDB_WRITE_QUEUE,
                max_items=settings.TSDB_WRITE_BATCH_SIZE,
                timeout=settings.TSDB_WRITE_BATCH_MAX_WAIT_SECONDS,
                queue_name='tsdb_write',
            )
            if not items:
                continue

            try:
                await cls._flush_batch(items)
            except Exception as exc:
                inc_queue_exception(queue_name='tsdb_write')
                log.error(f'时序数据库批量写入失败：工作线程={worker_id}，错误={exc}', exc_info=True)
            finally:
                for _ in items:
                    cls.TSDB_WRITE_QUEUE.task_done()

    @classmethod
    async def _flush_batch(cls, items: list[TSDBInsertItem]) -> None:
        sql_fragments = [
            item.table.insert_sql(subtable_name=item.subtable_name, values=item.values, tags=item.tags)
            for item in items
        ]
        first_sql, *rest_sql = sql_fragments
        sql = ' '.join([first_sql, *(fragment.removeprefix('INSERT INTO ') for fragment in rest_sql)])
        await tsdb.write(sql)
        observe_queue_size(cls.TSDB_WRITE_QUEUE, queue_name='tsdb_write')

    @classmethod
    async def shutdown(cls) -> None:
        for task in cls.TSDB_WRITER_TASKS:
            task.cancel()
        if cls.TSDB_WRITER_TASKS:
            await asyncio.gather(*cls.TSDB_WRITER_TASKS, return_exceptions=True)
        cls.TSDB_WRITER_TASKS.clear()
        cls.TSDB_WRITER_STARTED = False

        while True:
            try:
                cls.TSDB_WRITE_QUEUE.get_nowait()
                cls.TSDB_WRITE_QUEUE.task_done()
            except QueueEmpty:
                break

        observe_queue_size(cls.TSDB_WRITE_QUEUE, queue_name='tsdb_write')
        log.info('时序数据库写入器已停止')

    @classmethod
    def _get_selected_columns(cls, table: TSDBTable) -> tuple[tuple[str, ...], str]:
        column_names = tuple(field.name for field in table.columns)
        selected_columns = ', '.join(quote_identifier(name) for name in column_names)
        return column_names, selected_columns

    @classmethod
    def _build_query_sql(
            cls,
            *,
            table_name: str,
            selected_columns: str,
            filters: list[str],
            limit: int,
    ) -> str:
        where_sql = f" WHERE {' AND '.join(filters)}" if filters else ''
        return (
            f'SELECT {selected_columns} FROM {quote_identifier(table_name)}'
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
    async def insert(cls, message_ctx: MQTTMessageContext, *, payload: object) -> None:
        """将一条 MQTT 消息写入匹配的时序数据库子表。"""

        if not cls._ensure_tsdb_write_ready(action='消息写入'):
            log.debug('时序数据库未就绪，跳过消息写入')
            return

        route = parse_mqtt_topic(message_ctx.topic)
        if route is None:
            log.debug(f'消息主题无效，跳过写入：topic={message_ctx.topic}')
            return

        resolved_table = cls._resolve_model_table(route.model)
        if resolved_table is None:
            log.debug(f'未找到对应的数据模型，跳过写入：model={route.model}')
            return

        baby_id = await cls._resolve_baby_id(route.did)
        if baby_id is None:
            log.debug(f'未找到设备对应的宝宝 ID，跳过写入：did={route.did}')
            return

        model_key, table = resolved_table
        event_id = uuid.uuid4().hex
        try:
            item = TSDBInsertItem(
                table=table,
                subtable_name=cls._resolve_subtable_name(model_key, baby_id),
                tags=cls._build_insert_tags(baby_id=baby_id),
                values=cls._build_insert_values(
                    message_ctx=message_ctx,
                    route=route,
                    payload=payload,
                    event_id=event_id,
                ),
            )
            await asyncio.wait_for(
                cls.TSDB_WRITE_QUEUE.put(item),
                timeout=settings.TSDB_WRITE_ENQUEUE_TIMEOUT_SECONDS,
            )
            observe_queue_size(cls.TSDB_WRITE_QUEUE, queue_name='tsdb_write')
        except asyncio.TimeoutError:
            inc_queue_exception(queue_name='tsdb_write')
            log.warning(f'时序数据库写入队列入队超时，丢弃消息：{message_ctx.topic}')
        except Exception as exc:
            log.error(
                f'MQTT 消息写入时序数据库失败：数据表={table.name}，主题={message_ctx.topic}，错误={exc}'
            )

    @classmethod
    async def query(
            cls,
            *,
            model: str,
            baby_id: int,
            start_time: datetime | str | None = None,
            end_time: datetime | str | None = None,
            category: str | None = None,
            service: str | None = None,
            limit: int = 10000,
    ) -> list[dict[str, object]]:
        """从数据模型对应的时序数据库子表查询设备事件。"""

        resolved_table = cls._resolve_model_table(model)
        if resolved_table is None:
            return []

        if not cls._ensure_tsdb_read_ready(action='消息查询'):
            return []

        _, table = resolved_table
        range_start, range_end = cls._resolve_time_range(start_time=start_time, end_time=end_time)
        safe_limit = max(1, min(limit, cls.MAX_QUERY_ROWS))
        column_names, selected_columns = cls._get_selected_columns(table)
        filters = cls._build_query_filters(
            baby_id=baby_id,
            start_time=range_start,
            end_time=range_end,
            category=category,
            service=service,
        )

        sql = cls._build_query_sql(
            table_name=table.name,
            selected_columns=selected_columns,
            filters=filters,
            limit=safe_limit,
        )
        result = await tsdb.query(sql)
        rows = result.get('data', [])

        return cls._map_query_rows(column_names=column_names, rows=rows)
