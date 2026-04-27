# -*- coding: UTF-8 -*-
"""
Volcengine Viking Memory Async Client
"""

from __future__ import annotations

import asyncio

from datetime import datetime, timezone as datetime_timezone
from typing import Any, Awaitable, Callable

from backend.core.conf import settings
from backend.utils.timezone import timezone
from vikingdb.auth import APIKey
from vikingdb.memory.collection import Collection
from vikingdb.memory.client import VikingMem

MemoryResponse = dict[str, Any]
MemoryFilter = dict[str, Any]
MemoryBundle = dict[str, MemoryResponse]
MemoryTextBundle = dict[str, str]
FilterValue = str | list[str] | tuple[str, ...] | set[str] | None
TimeFilterValue = datetime | str | int | float | None
MemoryQuery = Callable[..., Awaitable[MemoryResponse]]

RESULT_LIST_KEYS = ('result_list', 'results', 'data')
MEMORY_TEXT_KEYS = (
    'summary', 'memory', 'content', 'text', 'value', 'question',
    'answer', 'profile', 'event', 'description', 'title', 'name',
)
MEMORY_ITEM_KEYS = ('memory_info', 'content', 'memory', 'event_id', 'profile_id')
TIMESTAMP_KEYS = ('event_time', 'updated_at', 'created_at', 'time', 'timestamp', 'ts')


class VikingMemoryClient:
    FILTER_USER_ID = 'user_id'
    FILTER_ASSISTANT_ID = 'assistant_id'
    FILTER_MEMORY_TYPE = 'memory_type'
    FILTER_START_TIME = 'start_time'
    FILTER_END_TIME = 'end_time'
    DEFAULT_EVENT_LIMIT = 10
    DEFAULT_PROFILE_LIMIT = 10
    MIN_LIMIT = 1
    MAX_LIMIT = 5000
    MAX_TEXT_FRAGMENTS = 8
    TIMESTAMP_OUTPUT_FORMAT = '%Y-%m-%d %H:%M:%S'

    def __init__(self) -> None:
        self._client: VikingMem | None = None
        self._collection: Collection | None = None

    @property
    def enabled(self) -> bool:
        return settings.VIKING_MEMORY_ENABLED

    @staticmethod
    def _normalize_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _normalize_filter_value(cls, value: FilterValue) -> str | list[str] | None:
        if value is None:
            return None

        if isinstance(value, (list, tuple, set)):
            items = [item for raw in value if (item := cls._normalize_text(raw)) is not None]
            if not items:
                return None
            return items[0] if len(items) == 1 else items

        return cls._normalize_text(value)

    @classmethod
    def _resolve_limit(cls, limit: int | None, default: int) -> int:
        resolved_limit = default if limit is None else limit
        return max(cls.MIN_LIMIT, min(resolved_limit, cls.MAX_LIMIT))

    @staticmethod
    def _normalize_timestamp_number(value: int | float) -> int:
        timestamp_value = float(value)
        if timestamp_value < 1_000_000_000_000:
            timestamp_value *= 1000
        return int(timestamp_value)

    @classmethod
    def _normalize_time_filter_value(cls, value: TimeFilterValue) -> int | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, (int, float)):
            return cls._normalize_timestamp_number(value)
        else:
            text = cls._normalize_text(value)
            if text is None:
                return None
            if text.isdigit():
                return cls._normalize_timestamp_number(int(text))
            try:
                parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
            except ValueError:
                return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.tz_info)
        return int(parsed.timestamp() * 1000)

    def _get_client(self) -> VikingMem:
        if self._client is None:
            self._client = VikingMem(
                host=settings.VIKING_MEMORY_HOST.strip(),
                region=settings.VIKING_MEMORY_REGION.strip(),
                scheme=settings.VIKING_MEMORY_SCHEME,
                timeout=int(settings.VIKING_MEMORY_TIMEOUT_SECONDS),
                auth=APIKey(api_key=settings.VIKING_MEMORY_API_KEY.get_secret_value().strip()),
            )
        return self._client

    def _get_collection(self) -> Collection:
        if self._collection is None:
            self._collection = self._get_client().get_collection(
                collection_name=settings.VIKING_MEMORY_COLLECTION_NAME.strip(),
                project_name=settings.VIKING_MEMORY_PROJECT_NAME.strip() or 'default',
            )
        return self._collection

    @classmethod
    def _build_filter(
            cls,
            *,
            user_id: str,
            assistant_id: FilterValue = None,
            memory_types: FilterValue = None,
            start_time: TimeFilterValue = None,
            end_time: TimeFilterValue = None,
            extra_filter: MemoryFilter | None = None,
    ) -> MemoryFilter:
        memory_filter = dict(extra_filter or {})
        memory_filter[cls.FILTER_USER_ID] = user_id

        if assistant_id_value := cls._normalize_filter_value(assistant_id):
            memory_filter[cls.FILTER_ASSISTANT_ID] = assistant_id_value

        if memory_type_value := cls._normalize_filter_value(memory_types):
            memory_filter[cls.FILTER_MEMORY_TYPE] = memory_type_value

        start_time_value = cls._normalize_time_filter_value(start_time)
        if start_time_value is not None:
            memory_filter[cls.FILTER_START_TIME] = start_time_value

        end_time_value = cls._normalize_time_filter_value(end_time)
        if end_time_value is not None:
            memory_filter[cls.FILTER_END_TIME] = end_time_value

        return memory_filter

    async def _query(
            self,
            query_fn: MemoryQuery,
            *,
            user_id: str,
            query: str | None = None,
            limit: int,
            assistant_id: FilterValue = None,
            memory_types: FilterValue = None,
            start_time: TimeFilterValue = None,
            end_time: TimeFilterValue = None,
            extra_filter: MemoryFilter | None = None,
            time_decay_config: dict[str, Any] | None = None,
    ) -> MemoryResponse:
        if not self.enabled:
            return {}

        params: dict[str, Any] = {
            'query': self._normalize_text(query),
            'filter': self._build_filter(
                user_id=user_id,
                assistant_id=assistant_id,
                memory_types=memory_types,
                start_time=start_time,
                end_time=end_time,
                extra_filter=extra_filter,
            ),
            'limit': limit,
        }
        if time_decay_config is not None:
            params['time_decay_config'] = time_decay_config

        rv = await query_fn(**params)
        return rv

    @classmethod
    def _extract_items(cls, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []

        for key in RESULT_LIST_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                items = cls._extract_items(value)
                if items:
                    return items

        if any(key in payload for key in MEMORY_ITEM_KEYS):
            return [payload]
        return []

    @classmethod
    def _extract_text(cls, payload: Any) -> str:
        if payload is None:
            return ''
        if isinstance(payload, str):
            return payload.strip()
        if isinstance(payload, (int, float, bool)):
            return str(payload)
        if isinstance(payload, list):
            parts = [cls._extract_text(item) for item in payload]
            return '; '.join(part for part in parts if part)
        if not isinstance(payload, dict):
            return str(payload).strip()

        for key in MEMORY_TEXT_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        fragments: list[str] = []
        for key, value in payload.items():
            text = cls._extract_text(value)
            if not text:
                continue
            if key in {'content', 'memory'}:
                fragments.append(text)
            else:
                fragments.append(f'{key}: {text}')
            if len(fragments) >= cls.MAX_TEXT_FRAGMENTS:
                break

        return '; '.join(fragments)

    @classmethod
    def _format_lines(cls, lines: list[str]) -> str:
        return '\n'.join(line for line in lines if line)

    @classmethod
    def _parse_timestamp(cls, value: Any) -> tuple[float, str]:
        if value is None:
            return 0.0, ''

        parsed: datetime | None = None

        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, (int, float)):
            timestamp_value = float(value)
            if timestamp_value > 1_000_000_000_000:
                timestamp_value /= 1000
            parsed = datetime.fromtimestamp(timestamp_value, tz=datetime_timezone.utc)
        elif isinstance(value, str):
            text = value.strip()
            if not text:
                return 0.0, ''
            if text.isdigit():
                timestamp_value = float(text)
                if timestamp_value > 1_000_000_000_000:
                    timestamp_value /= 1000
                parsed = datetime.fromtimestamp(timestamp_value, tz=datetime_timezone.utc)
            else:
                try:
                    parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
                except ValueError:
                    return 0.0, text

        if parsed is None:
            return 0.0, str(value).strip()

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime_timezone.utc)

        local_time = timezone.from_datetime(parsed)
        return local_time.timestamp(), local_time.strftime(cls.TIMESTAMP_OUTPUT_FORMAT)

    @classmethod
    def format_profile_memories(cls, payload: Any) -> str:
        lines: list[str] = []
        seen: set[str] = set()

        for item in cls._extract_items(payload):
            memory_text = cls._extract_text(item.get('memory_info')) or cls._extract_text(item)
            if not memory_text:
                continue

            memory_type = cls._normalize_text(item.get('memory_type') or item.get('profile_type'))
            line = f'{memory_type}: {memory_text}' if memory_type else memory_text
            if line in seen:
                continue

            seen.add(line)
            lines.append(line)

        return cls._format_lines(lines)

    @classmethod
    def format_event_memories(cls, payload: Any) -> str:
        entries: list[tuple[float, str]] = []
        seen: set[str] = set()

        for item in cls._extract_items(payload):
            memory_text = cls._extract_text(item.get('memory_info')) or cls._extract_text(item)
            if not memory_text:
                continue

            raw_timestamp, formatted_timestamp = cls._parse_timestamp(
                next((item.get(key) for key in TIMESTAMP_KEYS if item.get(key) is not None), None)
            )
            line = f'[{formatted_timestamp}] {memory_text}' if formatted_timestamp else memory_text
            if line in seen:
                continue

            seen.add(line)
            entries.append((raw_timestamp, line))

        entries.sort(key=lambda value: value[0], reverse=True)
        return cls._format_lines([line for _, line in entries])

    async def close(self) -> None:
        self._client = None
        self._collection = None

    async def query_event_memories(
            self,
            user_id: str,
            *,
            query: str | None = None,
            limit: int | None = None,
            assistant_id: FilterValue = None,
            start_time: TimeFilterValue = None,
            end_time: TimeFilterValue = None,
            extra_filter: MemoryFilter | None = None,
            time_decay_config: dict[str, Any] | None = None,
    ) -> MemoryResponse:
        return await self._query(
            self._get_collection().async_search_event_memory,
            user_id=user_id,
            query=query,
            limit=self._resolve_limit(limit, self.DEFAULT_EVENT_LIMIT),
            assistant_id=assistant_id,
            memory_types=settings.VIKING_MEMORY_EVENT_MEMORY_TYPES,
            start_time=start_time,
            end_time=end_time,
            extra_filter=extra_filter,
            time_decay_config=time_decay_config,
        )

    async def query_profile_memories(
            self,
            user_id: str,
            *,
            query: str | None = None,
            limit: int | None = None,
            assistant_id: FilterValue = None,
            start_time: TimeFilterValue = None,
            end_time: TimeFilterValue = None,
            extra_filter: MemoryFilter | None = None,
    ) -> MemoryResponse:
        return await self._query(
            self._get_collection().async_search_profile_memory,
            user_id=user_id,
            query=query,
            limit=self._resolve_limit(limit, self.DEFAULT_PROFILE_LIMIT),
            assistant_id=assistant_id,
            memory_types=settings.VIKING_MEMORY_PROFILE_MEMORY_TYPES,
            start_time=start_time,
            end_time=end_time,
            extra_filter=extra_filter,
        )

    async def query_event_memories_text(
            self,
            user_id: str,
            *,
            query: str | None = None,
            limit: int | None = None,
            assistant_id: FilterValue = None,
            start_time: TimeFilterValue = None,
            end_time: TimeFilterValue = None,
            extra_filter: MemoryFilter | None = None,
            time_decay_config: dict[str, Any] | None = None,
    ) -> str:
        payload = await self.query_event_memories(
            user_id,
            query=query,
            limit=limit,
            assistant_id=assistant_id,
            start_time=start_time,
            end_time=end_time,
            extra_filter=extra_filter,
            time_decay_config=time_decay_config,
        )
        formatted = self.format_event_memories(payload)
        return f"[用户事件]：\n{formatted}"

    async def query_profile_memories_text(
            self,
            user_id: str,
            *,
            query: str | None = None,
            limit: int | None = None,
            assistant_id: FilterValue = None,
            start_time: TimeFilterValue = None,
            end_time: TimeFilterValue = None,
            extra_filter: MemoryFilter | None = None,
    ) -> str:
        payload = await self.query_profile_memories(
            user_id,
            query=query,
            limit=limit,
            assistant_id=assistant_id,
            start_time=start_time,
            end_time=end_time,
            extra_filter=extra_filter,
        )

        formatted = self.format_profile_memories(payload)
        return f"[用户画像]：\n{formatted}"


viking_memory_client = VikingMemoryClient()


async def main():
    ret = await viking_memory_client.query_event_memories_text(
        user_id="1", query=''
    )
    print(ret)

    ret = await viking_memory_client.query_profile_memories_text(
        user_id="1", query=''
    )
    print(ret)


if __name__ == '__main__':
    asyncio.run(main())
