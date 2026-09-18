"""MQTT 公共配置、消息类型和回调类型。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeAlias

import paho.mqtt.client as mqtt
from paho.mqtt.properties import Properties

from backend.core.conf import settings


class MQTTVersion(Enum):
    """MQTT 协议版本。"""

    V311 = mqtt.MQTTv311
    V5 = mqtt.MQTTv5


@dataclass
class MQTTConfig:
    """MQTT 客户端配置。"""

    host: str = field(default_factory=lambda: settings.MQTT_HOST)
    port: int = field(default_factory=lambda: settings.MQTT_PORT)
    username: str | None = field(default_factory=lambda: settings.MQTT_USERNAME)
    password: str | None = None
    ssl: bool = False
    ssl_context: Any = None
    version: MQTTVersion = MQTTVersion.V5
    keepalive: int = 60
    reconnect_interval: int = 5
    max_reconnect_attempts: int = 12
    client_id: str | None = None
    backoff_max: int = 60
    backoff_jitter: float = 0.1
    unsubscribe_timeout: float = 5.0
    connection_timeout: float = 30.0
    request_max_pending: int = field(default_factory=lambda: settings.MQTT_REQUEST_MAX_PENDING)
    max_inflight_messages: int = field(default_factory=lambda: settings.MQTT_MAX_INFLIGHT_MESSAGES)
    max_queued_messages: int = field(default_factory=lambda: settings.MQTT_MAX_QUEUED_MESSAGES)


@dataclass
class MQTTMessageContext:
    """MQTT 消息上下文。"""

    topic: str
    payload: bytes
    qos: int
    retain: bool
    timestamp: float
    properties: Properties | None = None
    response_topic: str | None = None
    correlation_data: bytes | None = None


@dataclass(frozen=True, slots=True)
class MQTTPublishResult:
    """MQTT 发布结果。"""

    topic: str
    qos: int
    retain: bool
    mid: int | None
    published: bool
    error: str | None = None


MessageCallback: TypeAlias = Callable[[MQTTMessageContext], None | Awaitable[None]]
CallbackShardKeyExtractor: TypeAlias = Callable[[MQTTMessageContext], str | None]


class MQTTConnectionError(Exception):
    """MQTT 连接失败的自定义异常。"""


@dataclass(slots=True)
class MQTTSubscription:
    """单个 Topic 的订阅定义。"""

    topic: str
    qos: int
    callback: MessageCallback
    shard_key_extractor: CallbackShardKeyExtractor | None = None
