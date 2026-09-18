from __future__ import annotations

import asyncio
import json
from typing import Any

from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.reasoncodes import ReasonCode

from backend.app.cloud.service.device.gateway import DeviceGateway
from backend.common.mqtt import (
    MQTTClient,
    MQTTConfig,
    MQTTMessageContext,
    MQTTPublishResult,
    MQTTVersion,
)


class _PublishInfo:
    rc = 0
    mid = 7

    def is_published(self) -> bool:
        return True


class _PublishClient:
    def __init__(self, client: MQTTClient) -> None:
        self.client = client

    def publish(self, *args: Any, **kwargs: Any) -> _PublishInfo:
        self.client._on_publish(self, None, 7, ReasonCode(PacketTypes.PUBACK, 'Success'))
        return _PublishInfo()


def test_publish_waits_for_on_publish_and_checks_final_state() -> None:
    async def run() -> None:
        client = MQTTClient(MQTTConfig(version=MQTTVersion.V5))
        client._loop = asyncio.get_running_loop()
        client.connected = True
        client.client = _PublishClient(client)

        result = await client.publish('model/device/down/command', {'enabled': True}, timeout=0.2)

        assert result.published is True
        assert result.mid == 7
        assert not client._pending_publishes

    asyncio.run(run())


class _RequestClient(MQTTClient):
    def __init__(self) -> None:
        super().__init__(MQTTConfig(version=MQTTVersion.V5, request_max_pending=1))
        self.connected = True
        self.maximum_pending = 0
        self._response_subscribed.set()

    async def publish(
            self,
            topic: str,
            payload: str | dict | bytes | None = None,
            qos: int = 1,
            retain: bool = False,
            properties: Any = None,
            timeout: float | None = None,
    ) -> MQTTPublishResult:
        self.maximum_pending = max(self.maximum_pending, len(self._pending_requests))
        correlation_data = bytes(properties.CorrelationData)

        async def respond() -> None:
            await asyncio.sleep(0.02)
            self._resolve_pending_response(
                MQTTMessageContext(
                    topic=self._response_topic,
                    payload=b'{}',
                    qos=1,
                    retain=False,
                    timestamp=0,
                    correlation_data=correlation_data,
                )
            )

        asyncio.create_task(respond())
        return MQTTPublishResult(topic=topic, qos=qos, retain=retain, mid=1, published=True)


def test_request_pending_limit_and_deadline() -> None:
    async def run() -> None:
        client = _RequestClient()
        await asyncio.gather(*(client.request('model/device/down/request', {'index': i}) for i in range(3)))

        assert client.maximum_pending == 1
        assert not client._pending_requests

        client._response_subscribed.clear()
        started_at = asyncio.get_running_loop().time()
        try:
            await client.request('model/device/down/request', {}, timeout=0.03)
        except TimeoutError:
            elapsed = asyncio.get_running_loop().time() - started_at
        else:
            raise AssertionError('响应主题未订阅时，请求应在统一 deadline 内超时')

        assert elapsed < 0.1

    asyncio.run(run())


class _GatewayClient:
    def __init__(self) -> None:
        self.calls = 0
        self.active = 0
        self.maximum_active = 0

    async def request(self, **kwargs: Any) -> MQTTMessageContext:
        self.calls += 1
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        await asyncio.sleep(0.02)
        self.active -= 1
        return MQTTMessageContext(
            topic='server/response',
            payload=json.dumps({'success': True}).encode(),
            qos=1,
            retain=False,
            timestamp=0,
        )


def test_gateway_sends_independent_requests_without_merging(monkeypatch: Any) -> None:
    async def run() -> None:
        client = _GatewayClient()
        gateway = DeviceGateway(client)

        await asyncio.gather(
            *(
                gateway.request(
                    model='model',
                    did='device',
                    service='status',
                    action='get',
                    payload={'same': True},
                )
                for _ in range(5)
            )
        )

        assert client.calls == 5
        assert client.maximum_active == 5

    asyncio.run(run())


class _SubscriptionClient:
    def __init__(self) -> None:
        self.subscribe_calls: list[tuple[str, int]] = []
        self.unsubscribe_calls: list[str] = []

    def subscribe(self, topic: str, qos: int = 0) -> tuple[int, int]:
        self.subscribe_calls.append((topic, qos))
        return 0, len(self.subscribe_calls)

    def unsubscribe(self, topic: str) -> tuple[int, int]:
        self.unsubscribe_calls.append(topic)
        return 0, len(self.unsubscribe_calls)


def test_subscription_replaces_same_topic_and_unsubscribes_as_a_unit() -> None:
    async def run() -> None:
        mqtt_client = MQTTClient(MQTTConfig())
        paho_stub = _SubscriptionClient()
        mqtt_client.client = paho_stub
        mqtt_client.connected = True

        def first_callback(message: MQTTMessageContext) -> None:
            pass

        def second_callback(message: MQTTMessageContext) -> None:
            pass

        topic = '$share/group/js61/+/up/event'
        await mqtt_client.subscribe(topic, first_callback, qos=0)
        await mqtt_client.subscribe(topic, second_callback, qos=1)

        assert len(mqtt_client.subscriptions) == 1
        assert mqtt_client.subscriptions[topic].callback is second_callback
        assert mqtt_client.subscriptions[topic].qos == 1
        matcher_subscriptions = next(iter(mqtt_client._matcher.iter_match('js61/device/up/event')))
        assert list(matcher_subscriptions) == [topic]
        assert paho_stub.subscribe_calls == [(topic, 0), (topic, 1)]

        assert await mqtt_client.unsubscribe(topic) is True
        assert not mqtt_client.subscriptions
        assert list(mqtt_client._matcher.iter_match('js61/device/up/event')) == []
        assert paho_stub.unsubscribe_calls == [topic]

    asyncio.run(run())


def test_response_subscription_only_accepts_matching_successful_suback() -> None:
    client = MQTTClient(MQTTConfig())
    client._response_subscription_mid = 10
    success = ReasonCode(PacketTypes.SUBACK, 'Granted QoS 0')
    failure = ReasonCode(PacketTypes.SUBACK, 'Unspecified error')

    client._confirm_response_subscription(9, [success])
    assert client._response_subscribed.is_set() is False
    assert client._response_subscription_mid == 10

    client._confirm_response_subscription(10, [failure])
    assert client._response_subscribed.is_set() is False
    assert client._response_subscription_mid is None

    client._response_subscription_mid = 11
    client._confirm_response_subscription(11, [success])
    assert client._response_subscribed.is_set() is True
    assert client._response_subscription_mid is None
