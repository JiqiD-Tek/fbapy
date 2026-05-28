from __future__ import annotations

from backend.app.cloud.timeseries.event_store import EventStore
from backend.app.cloud.timeseries.mqtt_route import normalize_mqtt_payload, parse_mqtt_topic
from backend.app.cloud.timeseries.state_store import StateStore
from backend.common.log import log
from backend.common.mqtt_broker import MQTTBroker, MQTTMessageContext
from backend.core.conf import settings


class CloudMQTTConsumer:
    async def register(self, broker: MQTTBroker) -> None:
        for topic in settings.MQTT_UP_TOPICS:
            await broker.subscribe(topic, self.handle_message, shard_key_extractor=self.extract_shard_key)
            log.debug(f'已注册全局订阅: {topic}')

    @staticmethod
    def extract_shard_key(message_ctx: MQTTMessageContext) -> str | None:
        route = parse_mqtt_topic(message_ctx.topic)
        if route is None:
            return None
        return route.did

    async def handle_message(self, message_ctx: MQTTMessageContext) -> None:
        log.debug(f'收到全局消息 | 主题: {message_ctx.topic} | 内容: {message_ctx.payload}')

        route = parse_mqtt_topic(message_ctx.topic)
        if route is None or route.direction != 'up':
            return

        if route.category == 'property':
            await self._handle_property(route=route, message_ctx=message_ctx)
            return

        if route.category == 'event':
            await self._handle_event(route=route, message_ctx=message_ctx)

    @staticmethod
    async def _handle_property(*, route, message_ctx: MQTTMessageContext) -> None:
        try:
            payload = normalize_mqtt_payload(message_ctx.payload)
            await StateStore.update(
                route=route,
                payload=payload,
                timestamp=message_ctx.timestamp,
            )
        except Exception as exc:
            log.debug(f'更新设备状态失败: {exc}', exc_info=True)

    @staticmethod
    async def _handle_event(*, route, message_ctx: MQTTMessageContext) -> None:
        try:
            await StateStore.touch(
                route=route,
                timestamp=message_ctx.timestamp,
            )
        except Exception as exc:
            log.debug(f'更新设备状态时间戳失败: {exc}', exc_info=True)

        try:
            await EventStore.insert(message_ctx)
        except Exception as exc:
            log.debug(f'保存历史消息失败: {exc}', exc_info=True)


cloud_mqtt_consumer: CloudMQTTConsumer = CloudMQTTConsumer()
