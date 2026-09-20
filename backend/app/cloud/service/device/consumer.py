from __future__ import annotations

import json
import weakref

from backend.app.cloud.service.device.store import ShadowStore
from backend.app.cloud.service.device.topic import MQTTEventRoute, normalize_mqtt_payload, parse_mqtt_topic
from backend.app.cloud.telemetry.event_store import EventStore
from backend.common.log import log
from backend.common.mqtt import MQTTClient, MQTTMessageContext
from backend.core.conf import settings


class MQTTConsumer:
    """消费设备上行的属性和事件消息，并分发给状态与历史存储。"""

    def __init__(self) -> None:
        self._registered_topics: weakref.WeakKeyDictionary[MQTTClient, set[str]] = weakref.WeakKeyDictionary()

    @staticmethod
    def _decode_payload(payload: bytes) -> object:
        if not payload:
            return None

        try:
            payload_text = payload.decode('utf-8')
        except UnicodeDecodeError:
            return payload

        try:
            return json.loads(payload_text)
        except ValueError:
            return payload_text

    async def register(self, client: MQTTClient) -> None:
        """在指定 MQTTClient 上注册设备上行 Topic。"""
        registered_topics = self._registered_topics.setdefault(client, set())

        for topic in settings.MQTT_UP_TOPICS:
            if topic in registered_topics:
                continue
            await client.subscribe(topic, self.handle_message)
            registered_topics.add(topic)

    async def handle_message(self, message_ctx: MQTTMessageContext) -> None:
        """按照设备 Topic 类型处理一条上行消息。"""
        payload = self._decode_payload(message_ctx.payload)
        log.debug(f'收到设备上行消息 | 主题: {message_ctx.topic} | 内容: {payload}')

        route = parse_mqtt_topic(message_ctx.topic)
        if route is None or route.direction != 'up':
            return

        if route.category == 'property':
            await self._handle_property(route=route, payload=payload, message_ctx=message_ctx)
            return

        if route.category == 'event':
            await self._handle_event(route=route, payload=payload, message_ctx=message_ctx)

    @staticmethod
    async def _handle_property(
            *,
            route: MQTTEventRoute,
            payload: object,
            message_ctx: MQTTMessageContext,
    ) -> None:
        try:
            normalized_payload = normalize_mqtt_payload(payload)
            await ShadowStore.update(
                route=route,
                payload=normalized_payload,
                timestamp=message_ctx.timestamp,
            )
        except Exception as exc:
            log.debug(f'更新设备状态失败: {exc}', exc_info=True)

    @staticmethod
    async def _handle_event(
            *,
            route: MQTTEventRoute,
            payload: object,
            message_ctx: MQTTMessageContext,
    ) -> None:
        try:
            await ShadowStore.touch(
                route=route,
                timestamp=message_ctx.timestamp,
            )
        except Exception as exc:
            log.debug(f'更新设备状态时间戳失败: {exc}', exc_info=True)

        try:
            await EventStore.insert(message_ctx, payload=payload)
        except Exception as exc:
            log.debug(f'保存历史消息失败: {exc}', exc_info=True)


mqtt_consumer = MQTTConsumer()
