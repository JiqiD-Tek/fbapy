from __future__ import annotations

from dataclasses import dataclass
from typing import Any

VALID_MQTT_DIRECTIONS = frozenset({'up', 'down'})
VALID_MQTT_CATEGORIES = frozenset({'event', 'property'})


@dataclass(frozen=True, slots=True)
class MQTTEventRoute:
    """设备 MQTT Topic 中解析出的路由信息。"""

    model: str
    did: str
    direction: str
    category: str


def parse_mqtt_topic(topic: str) -> MQTTEventRoute | None:
    """解析 `{model}/{did}/{direction}/{category}` 格式的设备 Topic。"""
    parts = [segment.strip() for segment in str(topic).split('/') if segment.strip()]
    if len(parts) < 4:
        return None

    model, did, direction, category = parts[:4]
    if not model or not did or not direction or not category:
        return None

    if direction not in VALID_MQTT_DIRECTIONS:
        return None
    if category not in VALID_MQTT_CATEGORIES:
        return None

    return MQTTEventRoute(
        model=model.lower(),
        did=did,
        direction=direction,
        category=category,
    )


def normalize_mqtt_payload(payload: Any) -> Any:
    """将设备 Payload 转换为事件存储和状态影子支持的基础类型。"""
    if payload is None or isinstance(payload, (dict, list, str, int, float, bool)):
        return payload
    return str(payload)
