from __future__ import annotations

import json
import re

from dataclasses import asdict, dataclass, replace
from typing import Any, ClassVar

from backend.app.cloud.timeseries.mqtt_event import MQTTEventRoute
from backend.common.log import log
from backend.database.redis import redis_client


@dataclass(frozen=True, slots=True)
class DeviceStateSnapshot:
    did: str
    model: str
    timestamp: float
    online: bool | None = None
    battery: int | float | None = None
    volume: int | float | None = None
    storage: int | float | str | None = None
    sleep_duration: int | float | None = None
    sleep_song_count: int | None = None
    play_mode: str | None = None


class DeviceStateStore:
    STATE_REDIS_PREFIX: ClassVar[str] = 'fba:device:state'
    STATE_TTL_SECONDS: ClassVar[int] = 60 * 60 * 24
    STATE_FIELDS: ClassVar[tuple[str, ...]] = (
        'online', 'battery', 'volume', 'storage', 'sleep_duration', 'sleep_song_count', 'play_mode',
    )
    TRUE_VALUES: ClassVar[frozenset[str]] = frozenset({'1', 'true', 'yes', 'on', 'online'})
    FALSE_VALUES: ClassVar[frozenset[str]] = frozenset({'0', 'false', 'no', 'off', 'offline'})

    @classmethod
    def _cache_key(cls, did: str) -> str:
        return f'{cls.STATE_REDIS_PREFIX}:{did}'

    @classmethod
    def _prepare_payload(cls, payload: Any) -> Any:
        if isinstance(payload, str):
            text = payload.strip()
            if not text:
                return None
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text

        return payload

    @classmethod
    def _coerce_bool(cls, value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in {0, 1}:
            return bool(value)
        if isinstance(value, str):
            text = value.strip().lower()
            if text in cls.TRUE_VALUES:
                return True
            if text in cls.FALSE_VALUES:
                return False
        return None

    @staticmethod
    def _coerce_number(value: Any) -> int | float | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            if re.fullmatch(r'[-+]?\d+', text):
                return int(text)
            if re.fullmatch(r'[-+]?(?:\d+\.\d*|\d*\.\d+)', text):
                return float(text)
        return None

    @classmethod
    def _coerce_storage(cls, value: Any) -> int | float | str | None:
        number = cls._coerce_number(value)
        if number is not None:
            return number
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return None

    @classmethod
    def _coerce_int(cls, value: Any) -> int | None:
        number = cls._coerce_number(value)
        if number is None:
            return None
        return int(number)

    @staticmethod
    def _coerce_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _extract_state_patch(cls, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}

        patch: dict[str, Any] = {}

        if (online := cls._coerce_bool(payload.get('online'))) is not None:
            patch['online'] = online

        if (battery := cls._coerce_number(payload.get('battery'))) is not None:
            patch['battery'] = battery

        if (volume := cls._coerce_number(payload.get('volume'))) is not None:
            patch['volume'] = volume

        if (storage := cls._coerce_storage(payload.get('storage'))) is not None:
            patch['storage'] = storage

        if (sleep_duration := cls._coerce_number(payload.get('sleep_duration'))) is not None:
            patch['sleep_duration'] = sleep_duration

        if (sleep_song_count := cls._coerce_int(payload.get('sleep_song_count'))) is not None:
            patch['sleep_song_count'] = sleep_song_count

        if (play_mode := cls._coerce_text(payload.get('play_mode'))) is not None:
            patch['play_mode'] = play_mode

        return patch

    @classmethod
    def _deserialize_snapshot(cls, data: Any) -> DeviceStateSnapshot | None:
        if not isinstance(data, dict):
            return None

        did = cls._coerce_text(data.get('did'))
        model = cls._coerce_text(data.get('model'))
        timestamp = cls._coerce_number(data.get('timestamp'))
        if did is None or model is None or timestamp is None:
            return None

        return DeviceStateSnapshot(
            did=did,
            model=model,
            timestamp=float(timestamp),
            online=cls._coerce_bool(data.get('online')),
            battery=cls._coerce_number(data.get('battery')),
            volume=cls._coerce_number(data.get('volume')),
            storage=cls._coerce_storage(data.get('storage')),
            sleep_duration=cls._coerce_number(data.get('sleep_duration')),
            sleep_song_count=cls._coerce_int(data.get('sleep_song_count')),
            play_mode=cls._coerce_text(data.get('play_mode')),
        )

    @classmethod
    def _merge_snapshot(
            cls,
            *,
            did: str,
            model: str,
            current: DeviceStateSnapshot | None,
            patch: dict[str, Any],
            timestamp: float | None,
    ) -> DeviceStateSnapshot:
        resolved_timestamp = float(timestamp) if timestamp is not None else (current.timestamp if current else 0.0)
        base = current or DeviceStateSnapshot(
            did=did,
            model=model.lower(),
            timestamp=resolved_timestamp,
        )
        return replace(
            base,
            did=did,
            model=model.lower(),
            timestamp=resolved_timestamp,
            **{key: value for key, value in patch.items() if key in cls.STATE_FIELDS and value is not None},
        )

    @classmethod
    async def _load_snapshot(cls, did: str) -> DeviceStateSnapshot | None:
        raw = await redis_client.get(cls._cache_key(did))
        if not raw:
            return None
        try:
            return cls._deserialize_snapshot(json.loads(raw))
        except Exception as exc:
            log.debug(f'get device state failed, did={did}, error={exc}', exc_info=True)
            return None

    @classmethod
    async def update(cls, *, route: MQTTEventRoute, payload: Any, timestamp: float | None = None) -> None:
        if not route.did:
            return

        current = await cls._load_snapshot(route.did)
        patch = cls._extract_state_patch(cls._prepare_payload(payload))
        snapshot = cls._merge_snapshot(
            did=route.did,
            model=route.model,
            current=current,
            patch=patch,
            timestamp=timestamp,
        )

        try:
            await redis_client.set(
                cls._cache_key(route.did),
                json.dumps(asdict(snapshot), ensure_ascii=False, default=str),
                ex=cls.STATE_TTL_SECONDS,
            )
        except Exception as exc:
            log.debug(f'update device state failed, did={route.did}, error={exc}', exc_info=True)

    @classmethod
    async def get(cls, did: str) -> dict[str, Any] | None:
        snapshot = await cls._load_snapshot(did)
        if snapshot is None:
            return None
        return asdict(snapshot)
