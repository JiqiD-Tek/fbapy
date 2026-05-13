from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MQTTEventRoute:
    model: str
    did: str
    direction: str
    category: str


def parse_mqtt_topic(topic: str) -> MQTTEventRoute | None:
    parts = [segment.strip() for segment in str(topic).split('/') if segment.strip()]
    if len(parts) < 4:
        return None

    model, did, direction, category = parts[:4]
    if not model or not did or not direction or not category:
        return None

    return MQTTEventRoute(
        model=model.lower(),
        did=did,
        direction=direction.lower(),
        category=category.lower(),
    )


def normalize_payload(payload: Any) -> Any:
    if payload is None or isinstance(payload, (dict, list, str, int, float, bool)):
        return payload
    return str(payload)
