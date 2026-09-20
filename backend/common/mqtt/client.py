# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : mqtt/client.py
@Author  : guhua@jiqid.com
@Date    : 2025/09/12 11:22
"""

import asyncio
import inspect
import json
import uuid

from asyncio import Queue, QueueEmpty
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Any

import paho.mqtt.client as mqtt

from paho.mqtt.matcher import MQTTMatcher
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

from backend.common.log import log
from backend.common.mqtt.types import (
    MessageCallback,
    MQTTConfig,
    MQTTConnectionError,
    MQTTMessageContext,
    MQTTPublishResult,
    MQTTSubscription,
    MQTTVersion,
)
from backend.common.observability.prometheus.queue import inc_queue_exception, observe_queue_size
from backend.utils.timezone import timezone


@dataclass(slots=True)
class MQTTDispatchItem:
    callbacks: tuple[MessageCallback, ...]
    message_ctx: MQTTMessageContext


class MQTTClient:
    """
    一个支持自动重连和 asyncio 集成的 MQTT 客户端。
    它将 paho.mqtt.client 的同步回调桥接到 asyncio 事件循环。
    """

    def __init__(self, config: MQTTConfig) -> None:
        # 基础配置和 Paho 客户端。
        self.config = config
        self._client_id = self.config.client_id or f'fbapy_{uuid.uuid4().hex}'
        self.client: mqtt.Client | None = None

        # asyncio 生命周期状态。
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lifecycle_lock = asyncio.Lock()
        self._connected_event = asyncio.Event()

        # 业务订阅注册表；Paho 网络线程读取时由线程锁保护。
        self._callback_lock = Lock()
        self._subscriptions: dict[str, MQTTSubscription] = {}
        self._matcher = MQTTMatcher()

        # 有界队列和单个处理协程保证消息按入队顺序处理，并限制内存占用。
        self._callback_queue: Queue[MQTTDispatchItem] = Queue(maxsize=max(1, self.config.callback_queue_maxsize))
        self._callback_task: asyncio.Task | None = None

        # SUBSCRIBE 通过 MID 等待 SUBACK，确认 Broker 已接受业务主题订阅。
        self._pending_subscriptions: dict[int, asyncio.Future[None]] = {}
        self._pending_subscription_topics: dict[int, tuple[str, ...]] = {}

        # PUBLISH 通过 MID 等待 on_publish 回调，不占用 asyncio 默认线程池。
        self._pending_publishes: dict[int, asyncio.Future[None]] = {}

        # MQTT 5 请求发送后按 Correlation Data 等待对应响应。
        self._request_semaphore = asyncio.Semaphore(max(1, self.config.request_max_pending))
        self._pending_requests: dict[bytes, asyncio.Future[MQTTMessageContext]] = {}
        self._response_topic = f'fbapy/{self._client_id}/response'
        # 只有收到 SUBACK 后才允许 request() 发布，避免设备响应早于订阅到达。
        self._response_subscribed = asyncio.Event()
        self._response_subscription_mid: int | None = None
        self._response_subscription_error: MQTTConnectionError | None = None

    # ------------------------------------------------------------------
    # 公共状态和生命周期 API。
    # ------------------------------------------------------------------
    @property
    def connected(self) -> bool:
        """当前是否已经收到成功的 CONNACK。"""
        return self._connected_event.is_set()

    async def connect(self) -> bool:
        """启动 Paho 网络循环并等待首次连接成功。"""
        loop = asyncio.get_running_loop()
        async with self._lifecycle_lock:
            if self.connected:
                log.debug('已连接到 MQTT Client')
                return True

            if self._loop is not None and self._loop is not loop and self.client is not None:
                raise RuntimeError('MQTTClient 不能跨 asyncio 事件循环使用')
            self._loop = loop
            self._ensure_callback_worker()

            if self.client is None:
                self.client = self._create_paho_client()
                log.info(f'正在连接 MQTT Broker (ID: {self._client_id})')
                self.client.connect_async(self.config.host, self.config.port, keepalive=self.config.keepalive)
                self.client.loop_start()

        try:
            await asyncio.wait_for(self._connected_event.wait(), timeout=self.config.connection_timeout)
        except TimeoutError:
            log.error(f'MQTT 连接在 {self.config.connection_timeout}s 后超时')
            await self.disconnect()
            return False
        return self.connected

    async def disconnect(self) -> None:
        """关闭 Paho 网络循环，并结束所有等待中的操作。"""
        async with self._lifecycle_lock:
            client = self.client
            self.client = None
            self._connected_event.clear()
            self._reset_response_subscription()
            self._fail_pending_operations()

            if client is not None:
                def stop_client() -> None:
                    try:
                        client.disconnect()
                    finally:
                        client.loop_stop()

                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(stop_client),
                        timeout=self.config.shutdown_timeout,
                    )
                except TimeoutError:
                    log.warning(f'MQTT 客户端关闭超过 {self.config.shutdown_timeout}s')

            log.info('MQTT 客户端已断开连接')

        await self._shutdown_callback_worker()
        self._loop = None

    # ------------------------------------------------------------------
    # 公共消息 API：订阅、取消订阅、发布、请求-响应。
    # ------------------------------------------------------------------
    async def subscribe(
            self,
            topic: str,
            callback: MessageCallback,
            qos: int = 1,
    ) -> None:
        """
        订阅一个主题并注册回调函数。
        同一原始 Topic 重复注册时覆盖旧的回调和 QoS。
        """
        if not callable(callback):
            raise TypeError('callback 必须是可调用对象')
        qos = self._validate_qos(qos)
        actual_filter = self._extract_actual_filter(topic)

        with self._callback_lock:
            try:
                existing = self._matcher[actual_filter]
            except KeyError:
                existing = None
            if isinstance(existing, MQTTSubscription) and existing.topic != topic:
                raise ValueError(
                    f'实际 Topic Filter 已注册其他订阅: filter={actual_filter}, topic={existing.topic}'
                )

            previous = existing if isinstance(existing, MQTTSubscription) else None
            subscription = MQTTSubscription(topic=topic, qos=qos, callback=callback)
            self._subscriptions[topic] = subscription
            self._matcher[actual_filter] = subscription

        if not self.connected or not self.client:
            return

        mid: int | None = None
        try:
            mid, future = self._start_subscription(topic, topic_names=(topic,), qos=qos)
            await asyncio.wait_for(future, timeout=self.config.subscribe_timeout)
        except TimeoutError as exc:
            self._rollback_subscription(topic, actual_filter, subscription, previous)
            raise TimeoutError(f'MQTT 主题订阅确认超时: {topic}') from exc
        except Exception:
            self._rollback_subscription(topic, actual_filter, subscription, previous)
            raise
        finally:
            if mid is not None:
                self._pending_subscriptions.pop(mid, None)
                self._pending_subscription_topics.pop(mid, None)
        log.info(f'已订阅 MQTT 主题: {topic} (QoS: {qos})')

    async def unsubscribe(self, topic: str) -> bool:
        """取消一个 Topic 的订阅。"""
        with self._callback_lock:
            subscription = self._subscriptions.pop(topic, None)
            if subscription is None:
                log.warning(f'尝试取消不存在的 MQTT 订阅: {topic}')
                return False
            try:
                del self._matcher[self._extract_actual_filter(topic)]
            except KeyError:
                pass

        if self.client and self.connected:
            result, _mid = self.client.unsubscribe(topic)
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise MQTTConnectionError(f'MQTT 取消订阅发送失败: {mqtt.error_string(result)}')
            log.info(f'已发送 MQTT 取消订阅请求: {topic}')
        return True

    async def publish(
            self,
            topic: str,
            payload: str | dict | bytes | None = None,
            *,
            qos: int = 1,
            retain: bool = False,
            timeout: float | None = None,
            properties: Properties | None = None,
    ) -> MQTTPublishResult:
        """发布消息到指定主题，并等待 MQTT 发布确认。"""
        qos = self._validate_qos(qos)
        if not self.connected or not self.client:
            raise MQTTConnectionError('MQTT 客户端未连接')

        if payload is None:
            final_payload = None
        elif isinstance(payload, dict):
            final_payload = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        elif isinstance(payload, str):
            final_payload = payload.encode('utf-8')
        elif isinstance(payload, bytes):
            final_payload = payload
        else:
            raise TypeError('payload 必须是 dict、str、bytes 或 None')

        if properties is not None and self.config.version != MQTTVersion.V5:
            raise ValueError('MQTT Properties 仅支持 MQTT 5')

        info = self.client.publish(topic, final_payload, qos=qos, retain=retain, properties=properties)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise MQTTConnectionError(
                f'MQTT 发布发送失败: topic={topic}, mid={info.mid}, error={mqtt.error_string(info.rc)}'
            )

        ack_future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._pending_publishes[info.mid] = ack_future
        try:
            await asyncio.wait_for(
                ack_future,
                timeout=timeout if timeout is not None else self.config.publish_timeout,
            )
        except TimeoutError as exc:
            log.error(f'MQTT 发布确认超时: topic={topic}, mid={info.mid}')
            raise TimeoutError(f'MQTT 发布确认超时: topic={topic}, mid={info.mid}') from exc
        finally:
            self._pending_publishes.pop(info.mid, None)

        log.debug(f'已发布 MQTT 消息: topic={topic}, qos={qos}, retain={retain}, mid={info.mid}')
        return MQTTPublishResult(topic=topic, qos=qos, retain=retain, mid=info.mid)

    async def request(
            self,
            topic: str,
            payload: str | dict | bytes | None = None,
            *,
            qos: int = 1,
            timeout: float = 10.0,
    ) -> MQTTMessageContext:
        """发布 MQTT 5 请求，并等待通过 Correlation Data 关联的响应。

        响应主题订阅在连接成功时建立；请求只负责创建唯一关联数据、发布带
        Response Topic 的消息，并在超时或响应完成后清理 pending Future。
        """
        if self.config.version != MQTTVersion.V5:
            raise ValueError('request() 仅支持 MQTT 5')
        if timeout <= 0:
            raise ValueError('timeout 必须大于 0')

        qos = self._validate_qos(qos)
        if not self.connected:
            raise MQTTConnectionError('MQTT 客户端未连接')
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        semaphore_acquired = False
        correlation_data: bytes | None = None
        response_future: asyncio.Future[MQTTMessageContext] | None = None

        def remaining_timeout() -> float:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError('MQTT 请求超时')
            return remaining

        try:
            # 全局 pending 上限覆盖排队、发布和响应等待，避免高峰时 Future 无界增长。
            await asyncio.wait_for(self._request_semaphore.acquire(), timeout=remaining_timeout())
            semaphore_acquired = True

            # 先等待 SUBACK，确保设备的快速响应不会在响应主题订阅建立前丢失。
            await asyncio.wait_for(self._response_subscribed.wait(), timeout=remaining_timeout())
            if self._response_subscription_error is not None:
                raise self._response_subscription_error

            correlation_data = uuid.uuid4().bytes
            response_future = loop.create_future()
            self._pending_requests[correlation_data] = response_future

            # MQTT 5 标准请求-响应属性：设备应原样回传 CorrelationData。
            properties = Properties(PacketTypes.PUBLISH)
            properties.ResponseTopic = self._response_topic
            properties.CorrelationData = correlation_data

            await self.publish(
                topic=topic,
                payload=payload,
                qos=qos,
                properties=properties,
                timeout=remaining_timeout(),
            )
            return await asyncio.wait_for(response_future, timeout=remaining_timeout())
        finally:
            # 无论成功、超时还是发布失败，都必须移除 Future，防止内存泄漏。
            if correlation_data is not None:
                self._pending_requests.pop(correlation_data, None)
            if response_future is not None:
                if not response_future.done():
                    response_future.cancel()
                elif not response_future.cancelled():
                    # 发布阶段失败时，断线异常可能已写入响应 Future，需要显式消费。
                    response_future.exception()
            if semaphore_acquired:
                self._request_semaphore.release()

    # ------------------------------------------------------------------
    # Paho 客户端创建和网络线程回调。
    # ------------------------------------------------------------------
    def _create_paho_client(self) -> mqtt.Client:
        """创建由 Paho 原生网络循环负责自动重连的客户端。"""
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self._client_id,
            protocol=self.config.version.value,
            reconnect_on_failure=True,
        )
        client.reconnect_delay_set(
            min_delay=max(1, self.config.reconnect_interval),
            max_delay=max(self.config.reconnect_interval, self.config.backoff_max),
        )
        client.max_inflight_messages_set(max(1, self.config.max_inflight_messages))
        client.max_queued_messages_set(max(1, self.config.max_queued_messages))
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.on_subscribe = self._on_subscribe
        client.on_publish = self._on_publish

        if self.config.username:
            client.username_pw_set(self.config.username, self.config.password)
        if self.config.ssl:
            client.tls_set_context(self.config.ssl_context)
        return client

    def _on_connect(
            self,
            client: mqtt.Client,
            userdata: Any,
            flags: mqtt.ConnectFlags,
            reason_code: ReasonCode,
            properties: Properties | None = None,
    ) -> None:
        """接收 CONNACK，并将连接状态切回 asyncio 事件循环处理。"""
        if reason_code.is_failure:
            log.error(f'MQTT 连接被 Broker 拒绝: {reason_code}')
            self._call_loop_threadsafe(self._handle_connect_rejected, client)
            return
        self._call_loop_threadsafe(self._handle_connected, client)

    def _handle_connected(self, client: mqtt.Client) -> None:
        """在 asyncio 事件循环中恢复订阅并标记连接可用。"""
        if client is not self.client:
            return
        self._connected_event.set()
        self._resubscribe_all()
        if self.config.version == MQTTVersion.V5:
            self._subscribe_response_topic()
        log.info(f'成功连接到 MQTT Broker {self.config.host}:{self.config.port}')

    def _handle_connect_rejected(self, client: mqtt.Client) -> None:
        if client is self.client:
            self._connected_event.clear()

    def _on_disconnect(
            self,
            client: mqtt.Client,
            userdata: Any,
            flags: mqtt.DisconnectFlags,
            reason_code: ReasonCode,
            properties: Properties | None = None,
    ) -> None:
        """接收断线通知；意外断线后的重连由 Paho 网络循环负责。"""
        self._call_loop_threadsafe(self._handle_disconnected, client, reason_code)

    def _handle_disconnected(self, client: mqtt.Client, reason_code: ReasonCode) -> None:
        if client is not self.client:
            return
        self._connected_event.clear()
        self._reset_response_subscription()
        self._fail_pending_operations()
        if reason_code.is_failure:
            log.warning(f'MQTT 连接意外断开，Paho 将自动重连: {reason_code}')

    def _on_subscribe(
            self,
            client: mqtt.Client,
            userdata: Any,
            mid: int,
            reason_codes: list[ReasonCode],
            properties: Properties | None = None,
    ) -> None:
        """接收 SUBACK，并完成响应主题或业务主题对应的等待 Future。"""
        self._call_loop_threadsafe(self._resolve_subscription_ack, mid, reason_codes)

    def _resolve_subscription_ack(self, mid: int, reason_codes: list[ReasonCode]) -> None:
        """处理 SUBACK；Broker 拒绝订阅时使等待方立即失败。"""
        failure = next((code for code in reason_codes if code.is_failure), None)

        if mid == self._response_subscription_mid:
            self._response_subscription_mid = None
            if failure is not None:
                self._response_subscription_error = MQTTConnectionError(
                    f'MQTT 响应主题订阅被 Broker 拒绝: {failure}'
                )
                log.error(str(self._response_subscription_error))
            else:
                self._response_subscription_error = None
            # 成功和失败都唤醒 request()；失败原因由 request() 立即抛出。
            self._response_subscribed.set()
            return

        future = self._pending_subscriptions.pop(mid, None)
        topics = self._pending_subscription_topics.pop(mid, ())
        if future is None or future.done():
            return
        if failure is not None:
            future.set_exception(
                MQTTConnectionError(f'MQTT 主题订阅被 Broker 拒绝: topics={topics}, reason={failure}')
            )
        else:
            future.set_result(None)

    def _on_publish(
            self,
            client: mqtt.Client,
            userdata: Any,
            mid: int,
            reason_code: ReasonCode,
            properties: Properties | None = None,
    ) -> None:
        """收到发布确认后，在 asyncio 事件循环中完成对应 MID 的 Future。"""
        self._call_loop_threadsafe(self._resolve_publish_ack, mid, reason_code)

    def _resolve_publish_ack(self, mid: int, reason_code: ReasonCode) -> None:
        """将 Paho on_publish 回调转换为 asyncio Future 完成通知。"""
        future = self._pending_publishes.get(mid)
        if future is None or future.done():
            return
        if reason_code.is_failure:
            future.set_exception(MQTTConnectionError(f'MQTT 发布被 Broker 拒绝: {reason_code}'))
        else:
            future.set_result(None)

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        """将 Paho 网络线程收到的消息转交给请求 Future 或业务回调队列。"""
        topic = message.topic
        properties = getattr(message, 'properties', None)

        message_ctx = MQTTMessageContext(
            topic=topic,
            payload=bytes(message.payload or b''),
            qos=message.qos,
            retain=message.retain,
            timestamp=timezone.now().timestamp(),
            properties=properties,
            response_topic=getattr(properties, 'ResponseTopic', None),
            correlation_data=getattr(properties, 'CorrelationData', None),
        )

        # 请求响应直接完成对应 Future，不经过可能发生拥塞的业务回调队列。
        if topic == self._response_topic and message_ctx.correlation_data:
            self._call_loop_threadsafe(self._resolve_pending_response, message_ctx)

        callbacks: list[MessageCallback] = []
        with self._callback_lock:
            for subscription in self._matcher.iter_match(topic):
                if isinstance(subscription, MQTTSubscription):
                    callbacks.append(subscription.callback)

        if callbacks:
            self._call_loop_threadsafe(
                self._enqueue_dispatch_item_nowait,
                MQTTDispatchItem(callbacks=tuple(callbacks), message_ctx=message_ctx),
            )

    def _resolve_pending_response(self, message_ctx: MQTTMessageContext) -> None:
        """使用 MQTT 5 Correlation Data 将响应交给对应请求。"""
        future = self._pending_requests.get(bytes(message_ctx.correlation_data))
        if future is not None and not future.done():
            future.set_result(message_ctx)

    # ------------------------------------------------------------------
    # 订阅状态管理。
    # ------------------------------------------------------------------
    def _subscribe_response_topic(self) -> None:
        """连接成功后订阅客户端专用响应主题。"""
        if not self.connected or not self.client:
            return
        self._reset_response_subscription()
        result, mid = self.client.subscribe(self._response_topic, qos=1)
        if result != mqtt.MQTT_ERR_SUCCESS:
            self._response_subscription_error = MQTTConnectionError(
                f'MQTT 响应主题订阅发送失败: {mqtt.error_string(result)}'
            )
            log.error(str(self._response_subscription_error))
            self._response_subscribed.set()
            return
        # on_subscribe 会先调度回 asyncio 循环，因此这里会先保存 MID，再处理 SUBACK。
        self._response_subscription_mid = mid

    def _reset_response_subscription(self) -> None:
        """在 asyncio 线程中重置响应主题状态，避免与 SUBACK 回调并发修改。"""
        self._response_subscribed.clear()
        self._response_subscription_mid = None
        self._response_subscription_error = None

    def _start_subscription(
            self,
            topics: str | list[tuple[str, int]],
            *,
            topic_names: tuple[str, ...],
            qos: int = 1,
    ) -> tuple[int, asyncio.Future[None]]:
        """发送订阅并创建等待 SUBACK 的 Future。"""
        if not self.client or not self.connected:
            raise MQTTConnectionError('MQTT 客户端未连接')
        result, mid = self.client.subscribe(topics, qos=qos)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise MQTTConnectionError(f'MQTT 订阅发送失败: {mqtt.error_string(result)}')
        if mid is None:
            raise MQTTConnectionError('MQTT 订阅发送成功但未返回 MID')
        future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._pending_subscriptions[mid] = future
        self._pending_subscription_topics[mid] = topic_names
        return mid, future

    def _resubscribe_all(self) -> None:
        """重新订阅所有已注册的主题。"""
        if not self.client or not self.connected:
            return

        with self._callback_lock:
            topics_to_subscribe = [
                (subscription.topic, subscription.qos)
                for subscription in self._subscriptions.values()
            ]

        if not topics_to_subscribe:
            return

        try:
            topic_names = tuple(topic for topic, _qos in topics_to_subscribe)
            _mid, future = self._start_subscription(topics_to_subscribe, topic_names=topic_names)

            def consume_result(done: asyncio.Future[None]) -> None:
                try:
                    done.result()
                    log.info(f'已重新订阅 {len(topic_names)} 个 MQTT 主题')
                except Exception as exc:
                    log.error(f'MQTT 主题重新订阅失败: {exc}')

            future.add_done_callback(consume_result)
        except Exception as exc:
            log.error(f'MQTT 主题重新订阅发送失败: {exc}')

    def _rollback_subscription(
            self,
            topic: str,
            actual_filter: str,
            failed: MQTTSubscription,
            previous: MQTTSubscription | None,
    ) -> None:
        """订阅失败时恢复调用前的本地注册状态。"""
        with self._callback_lock:
            if self._subscriptions.get(topic) is not failed:
                return
            if previous is None:
                self._subscriptions.pop(topic, None)
                try:
                    del self._matcher[actual_filter]
                except KeyError:
                    pass
                return
            self._subscriptions[topic] = previous
            self._matcher[actual_filter] = previous

    def _fail_pending_operations(self) -> None:
        """连接断开时结束所有等待中的操作，避免协程无限等待。"""
        error_message = 'MQTT 客户端连接已断开'
        for future in self._pending_requests.values():
            if not future.done():
                future.set_exception(MQTTConnectionError(error_message))
        for future in self._pending_publishes.values():
            if not future.done():
                future.set_exception(MQTTConnectionError(error_message))
        for future in self._pending_subscriptions.values():
            if not future.done():
                future.set_exception(MQTTConnectionError(error_message))
        self._pending_requests.clear()
        self._pending_publishes.clear()
        self._pending_subscriptions.clear()
        self._pending_subscription_topics.clear()

    # ------------------------------------------------------------------
    # 业务回调队列。
    # ------------------------------------------------------------------
    def _ensure_callback_worker(self) -> None:
        if self._callback_task is not None and not self._callback_task.done():
            return
        self._callback_task = asyncio.create_task(self._callback_worker(), name='mqtt_callback_worker')
        self._observe_callback_queue_size()

    def _enqueue_dispatch_item_nowait(self, item: MQTTDispatchItem) -> None:
        try:
            self._callback_queue.put_nowait(item)
            self._observe_callback_queue_size()
        except asyncio.QueueFull:
            inc_queue_exception(queue_name='mqtt_callback')
            log.warning(f'MQTT 回调队列已满，丢弃消息: topic={item.message_ctx.topic}')

    async def _callback_worker(self) -> None:
        while True:
            item = await self._callback_queue.get()
            self._observe_callback_queue_size()
            try:
                await self._run_callback(item)
            except Exception as exc:
                inc_queue_exception(queue_name='mqtt_callback')
                log.error(f'MQTT 回调处理协程执行失败: {exc}', exc_info=True)
            finally:
                self._callback_queue.task_done()

    @staticmethod
    async def _run_callback(item: MQTTDispatchItem) -> None:
        for callback in item.callbacks:
            try:
                result = callback(item.message_ctx)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                inc_queue_exception(queue_name='mqtt_callback')
                callback_name = getattr(callback, '__qualname__', getattr(callback, '__name__', repr(callback)))
                log.error(
                    f'MQTT 业务回调执行失败: callback={callback_name}, '
                    f'topic={item.message_ctx.topic}, error={exc}',
                    exc_info=True,
                )

    async def _shutdown_callback_worker(self) -> None:
        task = self._callback_task
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self._callback_task = None

        while True:
            try:
                self._callback_queue.get_nowait()
                self._callback_queue.task_done()
            except QueueEmpty:
                break

        self._observe_callback_queue_size()

    def _observe_callback_queue_size(self) -> None:
        observe_queue_size(self._callback_queue, queue_name='mqtt_callback')

    # ------------------------------------------------------------------
    # 通用内部工具。
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_actual_filter(topic: str) -> str:
        """
        从订阅主题中提取实际的 Topic Filter，用于内部匹配。

        共享订阅格式为 $share/group/filter；内部匹配时只使用 filter 部分。
        """
        if topic.startswith('$share/'):
            parts = topic.split('/', 2)
            if len(parts) == 3:
                return parts[2]
        return topic

    @staticmethod
    def _validate_qos(qos: int) -> int:
        """校验 QoS 取值。"""
        if qos not in {0, 1, 2}:
            raise ValueError('qos 必须是 0、1 或 2')
        return qos

    def _call_loop_threadsafe(self, callback: Callable[..., Any], *args: Any) -> None:
        """在线程安全上下文调度回调到 asyncio 事件循环。"""
        loop = self._loop
        if loop and not loop.is_closed() and loop.is_running():
            loop.call_soon_threadsafe(callback, *args)
