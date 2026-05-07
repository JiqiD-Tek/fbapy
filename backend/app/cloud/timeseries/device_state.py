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
    power: str | None = None
    volume: int | float | None = None
    mute: bool | None = None
    player_state: str | None = None


class DeviceStateStore:
    STATE_REDIS_PREFIX: ClassVar[str] = 'fba:device:state'
    STATE_TTL_SECONDS: ClassVar[int] = 60 * 60 * 24
    STATE_FIELDS: ClassVar[tuple[str, ...]] = ('online', 'power', 'volume', 'mute', 'player_state')

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
    def _deserialize_snapshot(cls, data: Any) -> DeviceStateSnapshot | None:
        if not isinstance(data, dict):
            return None

        snapshot = DeviceStateSnapshot(
            did=data.get('did'),
            model=data.get('model'),
            timestamp=data.get('timestamp'),
            online=data.get('online'),
            power=data.get('power'),
            volume=data.get('volume'),
            mute=data.get('mute'),
            player_state=data.get('player_state'),
        )

        return snapshot

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
        base = current or DeviceStateSnapshot(
            did=did,
            model=model.lower(),
            timestamp=timestamp,
        )
        return replace(
            base,
            did=did,
            model=model.lower(),
            timestamp=timestamp,
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
        patch = cls._prepare_payload(payload)
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
