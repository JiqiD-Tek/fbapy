from __future__ import annotations

import asyncio

from typing import Any
from unittest.mock import AsyncMock

from backend.app.cloud.service.device.consumer import MQTTConsumer
from backend.app.cloud.service.device.store import ShadowStore
from backend.app.cloud.service.device.topic import parse_mqtt_topic
from backend.app.cloud.telemetry.event_store import EventStore
from backend.common.mqtt import MQTTMessageContext


def _message(topic: str, payload: bytes) -> MQTTMessageContext:
    return MQTTMessageContext(
        topic=topic,
        payload=payload,
        qos=1,
        retain=False,
        timestamp=123.0,
    )


def test_parse_device_mqtt_topic() -> None:
    route = parse_mqtt_topic('JS61/DEVICE_001/up/property')

    assert route is not None
    assert route.model == 'js61'
    assert route.did == 'DEVICE_001'
    assert route.direction == 'up'
    assert route.category == 'property'
    assert parse_mqtt_topic('JS61/DEVICE_001/up/unknown') is None


def test_device_consumer_routes_property_and_event(monkeypatch: Any) -> None:
    async def run() -> None:
        update = AsyncMock()
        touch = AsyncMock()
        insert = AsyncMock()
        monkeypatch.setattr(ShadowStore, 'update', update)
        monkeypatch.setattr(ShadowStore, 'touch', touch)
        monkeypatch.setattr(EventStore, 'insert', insert)

        consumer = MQTTConsumer()
        property_message = _message('js61/DEVICE_001/up/property', b'{"battery": 80}')
        event_message = _message('js61/DEVICE_001/up/event', b'{"service": "play"}')

        await consumer.handle_message(property_message)
        await consumer.handle_message(event_message)

        update.assert_awaited_once()
        property_call = update.await_args.kwargs
        assert property_call['route'].did == 'DEVICE_001'
        assert property_call['payload'] == {'battery': 80}
        assert property_call['timestamp'] == 123.0

        touch.assert_awaited_once()
        insert.assert_awaited_once_with(event_message, payload={'service': 'play'})

    asyncio.run(run())
