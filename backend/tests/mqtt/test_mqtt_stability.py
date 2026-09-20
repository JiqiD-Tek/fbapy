from __future__ import annotations

import asyncio
import json
from typing import Any

from paho.mqtt import client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.reasoncodes import ReasonCode

from backend.app.cloud.service.device.gateway import DeviceGateway
from backend.common.mqtt import (
    MQTTClient,
    MQTTConfig,
    MQTTConnectionError,
    MQTTMessageContext,
    MQTTPublishResult,
    MQTTVersion,
)


class _PublishInfo:
    rc = 0
    mid = 7


class _PublishClient:
    def __init__(self, client: MQTTClient) -> None:
        self.client = client

    def publish(self, *args: Any, **kwargs: Any) -> _PublishInfo:
        self.client._on_publish(self, None, 7, ReasonCode(PacketTypes.PUBACK, 'Success'))
        return _PublishInfo()


def test_publish_waits_for_on_publish() -> None:
    async def run() -> None:
        client = MQTTClient(MQTTConfig(version=MQTTVersion.V5))
        client._loop = asyncio.get_running_loop()
        client._connected_event.set()
        client.client = _PublishClient(client)

        result = await client.publish('model/device/down/command', {'enabled': True}, timeout=0.2)

        assert result.mid == 7
        assert not client._pending_publishes

    asyncio.run(run())


class _RequestClient(MQTTClient):
    def __init__(self) -> None:
        super().__init__(MQTTConfig(version=MQTTVersion.V5, request_max_pending=1))
        self._connected_event.set()
        self.maximum_pending = 0
        self._response_subscribed.set()

    async def publish(
            self,
            topic: str,
            payload: str | dict | bytes | None = None,
            *,
            qos: int = 1,
            retain: bool = False,
            timeout: float | None = None,
            properties: Any = None,
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
        return MQTTPublishResult(topic=topic, qos=qos, retain=retain, mid=1)


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
        self.request_topics: list[str] = []
        self.published_messages: list[dict[str, Any]] = []

    async def publish(self, **kwargs: Any) -> MQTTPublishResult:
        self.published_messages.append(kwargs)
        return MQTTPublishResult(
            topic=kwargs['topic'],
            qos=kwargs['qos'],
            retain=False,
            mid=1,
        )

    async def request(self, **kwargs: Any) -> MQTTMessageContext:
        self.calls += 1
        self.request_topics.append(kwargs['topic'])
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


def test_gateway_sends_independent_requests_without_merging() -> None:
    async def run() -> None:
        client = _GatewayClient()
        gateway = DeviceGateway(client, model='model', did='device')

        await asyncio.gather(
            *(
                gateway.request(
                    service='status',
                    action='get',
                    payload={'same': True},
                )
                for _ in range(5)
            )
        )

        assert client.calls == 5
        assert client.maximum_active == 5
        assert client.request_topics == ['model/device/down/request'] * 5

    asyncio.run(run())


def test_gateway_publish_builds_command_message() -> None:
    async def run() -> None:
        client = _GatewayClient()
        gateway = DeviceGateway(client, model='model', did='device')

        result = await gateway.publish(
            service='system',
            action='restart',
            payload={'delay': 1},
            qos=1,
        )

        assert len(client.published_messages) == 1
        published = client.published_messages[0]
        assert published['topic'] == 'model/device/down/command'
        assert published['qos'] == 1
        assert published['payload']['msg_id'] == result['request_id']
        assert published['payload']['service'] == 'system'
        assert published['payload']['payload'] == {'action': 'restart', 'delay': 1}
        assert result == {
            'request_id': published['payload']['msg_id'],
            'device_id': 'device',
            'success': True,
            'response': None,
            'topic': 'model/device/down/command',
        }

    asyncio.run(run())


class _SubscriptionClient:
    def __init__(self, client: MQTTClient, *, reason_name: str = 'Granted QoS 1') -> None:
        self.client = client
        self.reason_name = reason_name
        self.subscribe_calls: list[tuple[str, int]] = []
        self.unsubscribe_calls: list[str] = []

    def subscribe(self, topic: str, qos: int = 0) -> tuple[int, int]:
        self.subscribe_calls.append((topic, qos))
        mid = len(self.subscribe_calls)
        self.client._on_subscribe(
            self,
            None,
            mid,
            [ReasonCode(PacketTypes.SUBACK, self.reason_name)],
        )
        return 0, mid

    def unsubscribe(self, topic: str) -> tuple[int, int]:
        self.unsubscribe_calls.append(topic)
        return 0, len(self.unsubscribe_calls)


def test_subscription_replaces_same_topic_and_unsubscribes_as_a_unit() -> None:
    async def run() -> None:
        mqtt_client = MQTTClient(MQTTConfig())
        mqtt_client._loop = asyncio.get_running_loop()
        paho_stub = _SubscriptionClient(mqtt_client)
        mqtt_client.client = paho_stub
        mqtt_client._connected_event.set()

        def first_callback(message: MQTTMessageContext) -> None:
            pass

        def second_callback(message: MQTTMessageContext) -> None:
            pass

        topic = '$share/group/js61/+/up/event'
        await mqtt_client.subscribe(topic, first_callback, qos=0)
        await mqtt_client.subscribe(topic, second_callback, qos=1)

        assert len(mqtt_client._subscriptions) == 1
        assert mqtt_client._subscriptions[topic].callback is second_callback
        assert mqtt_client._subscriptions[topic].qos == 1
        matched_subscription = next(iter(mqtt_client._matcher.iter_match('js61/device/up/event')))
        assert matched_subscription.topic == topic
        assert paho_stub.subscribe_calls == [(topic, 0), (topic, 1)]

        assert await mqtt_client.unsubscribe(topic) is True
        assert not mqtt_client._subscriptions
        assert list(mqtt_client._matcher.iter_match('js61/device/up/event')) == []
        assert paho_stub.unsubscribe_calls == [topic]

    asyncio.run(run())


def test_subscription_fails_when_broker_rejects_topic() -> None:
    async def run() -> None:
        mqtt_client = MQTTClient(MQTTConfig())
        mqtt_client._loop = asyncio.get_running_loop()
        mqtt_client.client = _SubscriptionClient(mqtt_client, reason_name='Not authorized')
        mqtt_client._connected_event.set()

        try:
            await mqtt_client.subscribe('js61/+/up/event', lambda _message: None)
        except MQTTConnectionError as exc:
            assert 'Broker 拒绝' in str(exc)
        else:
            raise AssertionError('Broker 拒绝订阅时 subscribe() 应立即失败')

        assert not mqtt_client._subscriptions
        assert list(mqtt_client._matcher.iter_match('js61/device/up/event')) == []

    asyncio.run(run())


def test_response_subscription_records_matching_suback_result() -> None:
    client = MQTTClient(MQTTConfig())
    client._response_subscription_mid = 10
    success = ReasonCode(PacketTypes.SUBACK, 'Granted QoS 0')
    failure = ReasonCode(PacketTypes.SUBACK, 'Unspecified error')

    client._resolve_subscription_ack(9, [success])
    assert client._response_subscribed.is_set() is False
    assert client._response_subscription_mid == 10

    client._resolve_subscription_ack(10, [failure])
    assert client._response_subscribed.is_set() is True
    assert client._response_subscription_mid is None
    assert client._response_subscription_error is not None

    client._response_subscribed.clear()
    client._response_subscription_mid = 11
    client._resolve_subscription_ack(11, [success])
    assert client._response_subscribed.is_set() is True
    assert client._response_subscription_mid is None
    assert client._response_subscription_error is None


def test_request_fails_immediately_when_response_subscription_is_rejected() -> None:
    async def run() -> None:
        client = MQTTClient(MQTTConfig(version=MQTTVersion.V5, request_max_pending=1))
        client._connected_event.set()
        client._response_subscription_error = MQTTConnectionError('响应主题订阅被拒绝')
        client._response_subscribed.set()

        started_at = asyncio.get_running_loop().time()
        try:
            await client.request('model/device/down/request', {}, timeout=1)
        except MQTTConnectionError as exc:
            assert '响应主题订阅被拒绝' in str(exc)
        else:
            raise AssertionError('响应主题订阅失败时 request() 应立即失败')

        assert asyncio.get_running_loop().time() - started_at < 0.1
        assert not client._pending_requests

    asyncio.run(run())


def test_paho_client_uses_native_reconnect() -> None:
    client = MQTTClient(MQTTConfig(reconnect_interval=3, backoff_max=17))
    paho_client = client._create_paho_client()

    assert paho_client._reconnect_on_failure is True
    assert paho_client._reconnect_min_delay == 3
    assert paho_client._reconnect_max_delay == 17
    assert paho_client._callback_api_version == mqtt.CallbackAPIVersion.VERSION2
