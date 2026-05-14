from __future__ import annotations

import json

from dataclasses import asdict, dataclass, replace
from typing import Any, ClassVar

from backend.app.cloud.timeseries.mqtt_route import MQTTEventRoute
from backend.common.log import log
from backend.database.redis import redis_client


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    did: str
    model: str
    timestamp: int
    online: int | None = None
    battery: int | None = None
    volume: int | None = None
    storage_total: int | None = None
    storage_used: int | None = None
    sleep_mode: int | None = None
    sleep_value: int | None = None
    repeat_mode: int | None = None


class StateStore:
    STATE_REDIS_PREFIX: ClassVar[str] = 'fba:device:state'
    STATE_TTL_SECONDS: ClassVar[int] = 60 * 60 * 24
    STATE_FIELDS: ClassVar[tuple[str, ...]] = (
        'online', 'battery', 'volume', 'storage_total', 'storage_used', 'sleep_mode', 'sleep_value', 'repeat_mode',
    )

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
    def _coerce_int(cls, value: Any) -> int | None:
        if value is None:
            return None
        return int(value)

    @staticmethod
    def _coerce_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _resolve_storage_state(
            cls,
            payload: dict[str, Any],
    ) -> tuple[int | str | None, int | str | None]:
        storage_payload = payload.get('storage')
        if isinstance(storage_payload, dict):
            storage_total = cls._coerce_int(storage_payload.get('total'))
            storage_used = cls._coerce_int(storage_payload.get('used'))
            if storage_total is not None or storage_used is not None:
                return storage_total, storage_used

        return None, None

    @classmethod
    def _resolve_sleep_state(cls, payload: dict[str, Any]) -> tuple[int | None, int | None]:
        sleep_payload = payload.get('sleep')
        if isinstance(sleep_payload, dict):
            sleep_mode = cls._coerce_int(sleep_payload.get('mode'))
            sleep_value = cls._coerce_int(sleep_payload.get('value'))
            if sleep_mode is not None or sleep_value is not None:
                return sleep_mode, sleep_value

        return None, None

    @classmethod
    def _extract_state_patch(cls, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}

        patch: dict[str, Any] = {}

        if (online := cls._coerce_int(payload.get('online'))) is not None:
            patch['online'] = online

        if (battery := cls._coerce_int(payload.get('battery'))) is not None:
            patch['battery'] = battery

        if (volume := cls._coerce_int(payload.get('volume'))) is not None:
            patch['volume'] = volume

        storage_total, storage_used = cls._resolve_storage_state(payload)
        if storage_total is not None:
            patch['storage_total'] = storage_total
        if storage_used is not None:
            patch['storage_used'] = storage_used

        sleep_mode, sleep_value = cls._resolve_sleep_state(payload)
        if sleep_mode is not None:
            patch['sleep_mode'] = sleep_mode
        if sleep_value is not None:
            patch['sleep_value'] = sleep_value

        if (repeat_mode := cls._coerce_int(payload.get('repeat_mode'))) is not None:
            patch['repeat_mode'] = repeat_mode

        return patch

    @classmethod
    def _deserialize_snapshot(cls, data: Any) -> StateSnapshot | None:
        if not isinstance(data, dict):
            return None

        did = cls._coerce_text(data.get('did'))
        model = cls._coerce_text(data.get('model'))
        timestamp = cls._coerce_int(data.get('timestamp'))
        if did is None or model is None or timestamp is None:
            return None

        storage_total, storage_used = cls._resolve_storage_state(data)
        sleep_mode, sleep_value = cls._resolve_sleep_state(data)

        return StateSnapshot(
            did=did,
            model=model,
            timestamp=timestamp,
            online=cls._coerce_int(data.get('online')),
            battery=cls._coerce_int(data.get('battery')),
            volume=cls._coerce_int(data.get('volume')),
            storage_total=storage_total,
            storage_used=storage_used,
            sleep_mode=sleep_mode,
            sleep_value=sleep_value,
            repeat_mode=cls._coerce_int(data.get('repeat_mode')),
        )

    @classmethod
    def _merge_snapshot(
            cls,
            *,
            did: str,
            model: str,
            current: StateSnapshot | None,
            patch: dict[str, Any],
            timestamp: float | None,
    ) -> StateSnapshot:
        resolved_timestamp = float(timestamp) if timestamp is not None else (current.timestamp if current else 0.0)
        base = current or StateSnapshot(
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
    async def _load_snapshot(cls, did: str) -> StateSnapshot | None:
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
