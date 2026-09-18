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
import math
import random
import uuid
import zlib

from asyncio import Queue, QueueEmpty
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from threading import Lock
from typing import Any

import paho.mqtt.client as mqtt

from paho.mqtt.matcher import MQTTMatcher
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

from backend.common.log import log
from backend.common.observability.prometheus.queue import inc_queue_exception, observe_queue_size
from backend.core.conf import settings
from backend.utils.timezone import timezone
from backend.common.mqtt.types import (
    CallbackShardKeyExtractor,
    MessageCallback,
    MQTTConfig,
    MQTTConnectionError,
    MQTTMessageContext,
    MQTTPublishResult,
    MQTTSubscription,
    MQTTVersion,
)


@dataclass(slots=True)
class MQTTDispatchItem:
    callbacks: tuple[MessageCallback, ...]
    message_ctx: MQTTMessageContext


@dataclass(slots=True)
class _QueueGroupView:
    queues: tuple[Queue[Any], ...]

    def qsize(self) -> int:
        return sum(queue.qsize() for queue in self.queues)


class MQTTClient:
    """
    一个支持自动重连和 asyncio 集成的 MQTT 客户端。
    它将 paho.mqtt.client 的同步回调桥接到 asyncio 事件循环。
    """

    def __init__(self, config: MQTTConfig) -> None:
        self.config = config
        self.client: mqtt.Client | None = None
        self.connected = False
        self.reconnect_attempts = 0
        self._client_id = self.config.client_id or f'fbapy_{uuid.uuid4().hex}'

        # 每个原始 Topic 只维护一个订阅定义；重复注册同一 Topic 时覆盖旧定义。
        self.subscriptions: dict[str, MQTTSubscription] = {}
        # MQTTMatcher 存储的是实际的 topic filter (不含 $share/group/)
        # value 以原始 Topic 为 key，兼容共享订阅和普通订阅映射到同一 filter。
        self._matcher = MQTTMatcher()
        self._matcher_subscriptions: dict[str, dict[str, MQTTSubscription]] = {}

        # 异步事件用于控制连接循环
        self._connection_event = asyncio.Event()  # 连接成功时设置
        self._disconnect_event = asyncio.Event()  # 意外断开时设置
        self._stop_event = asyncio.Event()  # 外部请求停止时设置

        # 锁
        self._client_lock = asyncio.Lock()  # 保护 client 对象的创建/销毁和连接/断开操作
        self._callback_lock = Lock()  # 保护 self.subscriptions 和 self._matcher，被 paho-mqtt 线程访问

        self._connection_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._callback_shards = max(1, settings.MQTT_CALLBACK_SHARDS)
        self._callback_queue_maxsize = max(1, settings.MQTT_CALLBACK_QUEUE_MAXSIZE)
        self._callback_queue_shard_maxsize = max(1, math.ceil(self._callback_queue_maxsize / self._callback_shards))
        self._callback_queues: list[Queue[MQTTDispatchItem]] = [
            Queue(maxsize=self._callback_queue_shard_maxsize) for _ in range(self._callback_shards)
        ]
        self._callback_queue_view = _QueueGroupView(tuple(self._callback_queues))
        self._callback_tasks: list[asyncio.Task] = []
        self._callback_started = False
        self._callback_start_lock = asyncio.Lock()

        # 请求发送后暂存 Future；响应收到后按 Correlation Data 完成对应 Future。
        self._pending_requests: dict[bytes, asyncio.Future[MQTTMessageContext]] = {}
        self._request_semaphore = asyncio.Semaphore(max(1, self.config.request_max_pending))
        # publish() 通过 MID 等待 on_publish 回调，不占用 asyncio 默认线程池。
        self._pending_publishes: dict[int, asyncio.Future[None]] = {}
        # 每个客户端使用独立响应主题，避免多实例部署时响应被其他实例消费。
        self._response_topic = f'fbapy/{self._client_id}/response'
        # 只有收到 SUBACK 后才允许 request() 发布，避免设备响应早于订阅到达。
        self._response_subscribed = asyncio.Event()
        self._response_subscription_mid: int | None = None

    # ------------------------------------------------------------------
    # 回调队列：把 Paho 线程中的消息安全地转交给 asyncio。
    # ------------------------------------------------------------------
    async def _ensure_callback_workers(self) -> None:
        if self._callback_started:
            return

        async with self._callback_start_lock:
            if self._callback_started:
                return

            self._callback_tasks = [
                asyncio.create_task(
                    self._callback_worker(shard_id=shard_id),
                    name=f'mqtt_callback_worker_{shard_id}',
                )
                for shard_id in range(self._callback_shards)
            ]
            self._callback_started = True
            self._observe_callback_queue_sizes()

    def _observe_callback_queue_sizes(self) -> None:
        observe_queue_size(self._callback_queue_view, queue_name='mqtt_callback')

    @staticmethod
    def _resolve_shard_id_from_key(shard_key: str, shard_count: int) -> int:
        return zlib.crc32(shard_key.encode('utf-8')) % shard_count

    def _resolve_callback_shard_id(
            self,
            *,
            message_ctx: MQTTMessageContext,
            shard_key_extractor: CallbackShardKeyExtractor | None,
    ) -> int:
        shard_key: str | None = None
        if shard_key_extractor is not None:
            try:
                shard_key = shard_key_extractor(message_ctx)
            except Exception as exc:
                log.error(f'MQTT shard key extractor failed: {exc}', exc_info=True)

        if shard_key:
            return self._resolve_shard_id_from_key(shard_key, self._callback_shards)

        return self._resolve_shard_id_from_key(message_ctx.topic, self._callback_shards)

    def _enqueue_dispatch_item_nowait(self, shard_id: int, item: MQTTDispatchItem) -> None:
        queue = self._callback_queues[shard_id]
        try:
            queue.put_nowait(item)
            self._observe_callback_queue_sizes()
        except asyncio.QueueFull:
            inc_queue_exception(queue_name='mqtt_callback')
            log.warning(
                f'MQTT callback shard queue is full, dropping message: shard={shard_id}, topic={item.message_ctx.topic}'
            )

    def _enqueue_dispatch_items_nowait(self, items: list[tuple[int, MQTTDispatchItem]]) -> None:
        for shard_id, item in items:
            self._enqueue_dispatch_item_nowait(shard_id, item)

    async def _callback_worker(self, *, shard_id: int) -> None:
        queue = self._callback_queues[shard_id]
        while True:
            item = await queue.get()
            self._observe_callback_queue_sizes()
            try:
                await self._run_callback(item)
            except Exception as exc:
                inc_queue_exception(queue_name='mqtt_callback')
                log.error(f'MQTT callback worker failed: shard={shard_id}, error={exc}', exc_info=True)
            finally:
                queue.task_done()

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
                    f'MQTT callback failed: callback={callback_name}, topic={item.message_ctx.topic}, error={exc}',
                    exc_info=True)

    async def _shutdown_callback_workers(self) -> None:
        for task in self._callback_tasks:
            task.cancel()

        if self._callback_tasks:
            await asyncio.gather(*self._callback_tasks, return_exceptions=True)

        self._callback_tasks.clear()
        self._callback_started = False

        for queue in self._callback_queues:
            while True:
                try:
                    queue.get_nowait()
                    queue.task_done()
                except QueueEmpty:
                    break

        self._observe_callback_queue_sizes()

    # ------------------------------------------------------------------
    # 连接生命周期。
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # 公共生命周期 API：连接在初始化阶段调用，断开和 context 在文件后部实现。
    # ------------------------------------------------------------------
    async def connect(self) -> bool:
        """
        连接 MQTT Client。
        如果已连接，则直接返回 True。
        如果连接任务正在进行，则等待其完成。
        """
        self._loop = asyncio.get_running_loop()
        await self._ensure_callback_workers()

        async with self._client_lock:
            if self.connected:
                log.debug('已连接到 MQTT Client')
                return True

            if self._connection_task and not self._connection_task.done():
                log.debug('连接任务已在进行中，等待连接事件...')
            else:
                # 启动新的连接循环
                self._stop_event.clear()
                self._connection_event.clear()
                self._disconnect_event.clear()
                self._connection_task = self._loop.create_task(
                    self._connection_loop(), name='mqtt_connection_loop'
                )

        try:
            # 等待连接成功事件
            await asyncio.wait_for(self._connection_event.wait(), timeout=self.config.connection_timeout)
        except asyncio.TimeoutError:
            log.error(f'连接在 {self.config.connection_timeout}s 后超时')
            # 连接超时后在锁外清理，避免重入死锁
            await self.disconnect()
            return False
        except Exception as e:
            log.error(f'连接过程中发生意外错误: {e}', exc_info=True)
            await self.disconnect()
            return False
        else:
            return self.connected

    # ------------------------------------------------------------------
    # Paho 回调：只做轻量状态更新，并将工作切回 asyncio 事件循环。
    # ------------------------------------------------------------------
    def _on_connect(
            self, client: mqtt.Client, userdata: Any, flags: mqtt.ConnectFlags, reason_code: ReasonCode,
            properties: Properties | None = None,
    ) -> None:
        """客户端连接到 Client 时的回调。"""
        with self._callback_lock:
            if not reason_code.is_failure:
                self.connected = True
                self.reconnect_attempts = 0
                # 成功连接后，重新订阅所有主题
                self._submit_coroutine_threadsafe(self._resubscribe_all())
                # Paho 回调在线程中执行，切回 asyncio 事件循环订阅专用响应主题。
                self._call_loop_threadsafe(self._subscribe_response_topic)
                # 设置连接事件，唤醒等待 connect() 的协程
                self._call_loop_threadsafe(self._connection_event.set)
                log.info(f'成功连接到 MQTT Client {self.config.host}:{self.config.port}')
            else:
                log.error(f'连接失败: {reason_code}')
                self.connected = False
                # 清除连接事件，确保 connect() 失败
                self._call_loop_threadsafe(self._connection_event.clear)

    def _on_disconnect(
            self, client: mqtt.Client, userdata: Any, flags: mqtt.DisconnectFlags, reason_code: ReasonCode,
            properties: Properties | None = None,
    ) -> None:
        """客户端断开连接时的回调。"""
        with self._callback_lock:
            self.connected = False
            # 断线后清除订阅完成标记，阻止新的 request 在重连完成前发送。
            self._call_loop_threadsafe(self._reset_response_subscription)
            # 在事件循环中结束所有等待响应的 Future，避免请求永久挂起。
            self._call_loop_threadsafe(self._fail_pending_requests)
            # 清除连接事件
            self._call_loop_threadsafe(self._connection_event.clear)
            # 触发断开事件，通知连接循环醒来
            self._call_loop_threadsafe(self._disconnect_event.set)
            if reason_code.is_failure:
                log.warning(f'意外断开连接: {reason_code}')

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        """接收到消息时的回调。"""
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

        # Paho 回调运行在线程中，必须切回 asyncio 事件循环后操作 Future。
        if topic == self._response_topic and message_ctx.correlation_data:
            self._call_loop_threadsafe(self._resolve_pending_response, message_ctx)

        # 2. 查找匹配的回调函数，并按分片交给有界调度队列
        dispatch_items: list[tuple[int, MQTTDispatchItem]] = []
        with self._callback_lock:
            # 使用 MQTTMatcher 查找所有匹配该主题的订阅回调
            for subscriptions in self._matcher.iter_match(topic):
                if not isinstance(subscriptions, dict):
                    continue
                shard_buckets: dict[int, list[MessageCallback]] = {}
                for subscription in subscriptions.values():
                    shard_id = self._resolve_callback_shard_id(
                        message_ctx=message_ctx,
                        shard_key_extractor=subscription.shard_key_extractor,
                    )
                    shard_buckets.setdefault(shard_id, []).append(subscription.callback)

                dispatch_items.extend(
                    (
                        shard_id,
                        MQTTDispatchItem(
                            callbacks=tuple(bucket_callbacks),
                            message_ctx=message_ctx,
                        ),
                    )
                    for shard_id, bucket_callbacks in shard_buckets.items()
                )

        if dispatch_items:
            self._call_loop_threadsafe(self._enqueue_dispatch_items_nowait, dispatch_items)

    def _on_subscribe(self, client: mqtt.Client, userdata: Any, mid: int, reason_codes: list[ReasonCode],
                      properties: Properties | None = None) -> None:
        """接收 SUBACK，确认专用响应主题已经可用。"""
        self._call_loop_threadsafe(self._confirm_response_subscription, mid, reason_codes)

    def _on_publish(self, client: mqtt.Client, userdata: Any, mid: int, reason_code: ReasonCode,
                    properties: Properties | None = None) -> None:
        """收到发布确认后，在 asyncio 事件循环中完成对应 MID 的 Future。"""
        self._call_loop_threadsafe(self._resolve_publish_ack, mid, reason_code)

    def _confirm_response_subscription(self, mid: int, reason_codes: list[ReasonCode]) -> None:
        """处理 SUBACK 结果；拒绝订阅时保持 Event 未设置，让请求超时失败。"""
        if mid != self._response_subscription_mid:
            return
        self._response_subscription_mid = None
        if any(reason_code.is_failure for reason_code in reason_codes):
            log.error('MQTT 响应主题订阅被 Client 拒绝')
            return
        self._response_subscribed.set()

    def _subscribe_response_topic(self) -> None:
        """连接成功后订阅客户端专用响应主题。"""
        if not self.connected or not self.client:
            return
        self._response_subscribed.clear()
        result, mid = self.client.subscribe(self._response_topic, qos=1)
        if result != mqtt.MQTT_ERR_SUCCESS:
            log.error(f'MQTT 响应主题订阅失败: {mqtt.error_string(result)}')
            return
        # on_subscribe 会先调度回 asyncio 循环，因此这里会先保存 MID，再处理 SUBACK。
        self._response_subscription_mid = mid

    def _reset_response_subscription(self) -> None:
        """在 asyncio 线程中重置响应主题状态，避免与 SUBACK 回调并发修改。"""
        self._response_subscribed.clear()
        self._response_subscription_mid = None

    def _resolve_publish_ack(self, mid: int, reason_code: ReasonCode) -> None:
        """将 Paho on_publish 回调转换为 asyncio Future 完成通知。"""
        future = self._pending_publishes.get(mid)
        if future is None or future.done():
            return
        if reason_code.is_failure:
            future.set_exception(MQTTConnectionError(f'MQTT publish failed: {reason_code}'))
        else:
            future.set_result(None)

    def _fail_pending_requests(self) -> None:
        """连接断开时结束所有等待中的请求，避免协程无限等待。"""
        for future in self._pending_requests.values():
            if not future.done():
                future.set_exception(MQTTConnectionError('mqtt client disconnected'))
        for future in self._pending_publishes.values():
            if not future.done():
                future.set_exception(MQTTConnectionError('mqtt client disconnected'))

    def _resolve_pending_response(self, message_ctx: MQTTMessageContext) -> None:
        """使用 MQTT 5 Correlation Data 将响应交给对应请求。"""
        future = self._pending_requests.get(bytes(message_ctx.correlation_data))
        if future is not None and not future.done():
            future.set_result(message_ctx)

    # ------------------------------------------------------------------
    # 内部工具和状态转换。
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_actual_filter(topic: str) -> str:
        """
        从订阅主题中提取实际的 topic filter，用于内部匹配。
        如果主题是共享订阅格式 ($share/group/filter)，则返回 filter 部分。
        否则返回原主题。
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

    @staticmethod
    def _consume_threadsafe_future(future: Any) -> None:
        """消费 run_coroutine_threadsafe 的 future，避免异常静默。"""
        try:
            future.result()
        except Exception as e:
            log.error(f'线程安全协程调度失败: {e}', exc_info=True)

    def _call_loop_threadsafe(self, callback: Callable[..., Any], *args: Any) -> None:
        """在线程安全上下文调度回调到事件循环。"""
        loop = self._loop
        if loop and not loop.is_closed() and loop.is_running():
            loop.call_soon_threadsafe(callback, *args)

    def _submit_coroutine_threadsafe(self, coro: Awaitable[Any]) -> None:
        """在线程安全上下文调度协程到事件循环。"""
        loop = self._loop
        if not loop or loop.is_closed() or not loop.is_running():
            if asyncio.iscoroutine(coro):
                coro.close()
            return
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        future.add_done_callback(self._consume_threadsafe_future)

    async def _connection_loop(self) -> None:
        """核心连接循环，负责连接、重连和保持连接。"""
        while not self._stop_event.is_set():
            try:
                # 1. 准备客户端
                log.info(f'正在尝试连接 MQTT Client (ID: {self._client_id})')

                self.client = mqtt.Client(
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                    client_id=self._client_id,
                    protocol=self.config.version.value,
                    # 重连只由 _connection_loop 管理，避免和 Paho 的自动重连互相竞争。
                    reconnect_on_failure=False,
                )
                # 对 Paho 本地积压设置硬上限，Client 不可用时不允许消息无限占用内存。
                self.client.max_inflight_messages_set(max(1, self.config.max_inflight_messages))
                self.client.max_queued_messages_set(max(1, self.config.max_queued_messages))
                self.client.on_connect = self._on_connect  # 连接成功
                self.client.on_disconnect = self._on_disconnect  # 连接断开
                self.client.on_message = self._on_message  # 收到消息
                self.client.on_subscribe = self._on_subscribe  # 订阅确认
                self.client.on_publish = self._on_publish  # 发布完成

                if self.config.username and self.config.password:
                    self.client.username_pw_set(self.config.username, self.config.password)

                if self.config.ssl:
                    self.client.tls_set_context(self.config.ssl_context)

                # 2. 建立连接并启动后台循环
                self.client.connect(self.config.host, self.config.port, keepalive=self.config.keepalive)
                self.client.loop_start()

                # 3. 等待连接成功
                await asyncio.wait_for(self._connection_event.wait(), timeout=self.config.connection_timeout)

                # 4. 挂起协程，直到断开连接或外部停止
                self._disconnect_event.clear()
                disconnect_task = self._loop.create_task(self._disconnect_event.wait(), name='mqtt_disconnect_wait')
                stop_task = self._loop.create_task(self._stop_event.wait(), name='mqtt_stop_wait')
                _, pending = await asyncio.wait({disconnect_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)

            except asyncio.TimeoutError:
                log.error('MQTT 连接超时')
            except (OSError, ValueError) as e:
                log.error(f'MQTT 连接失败: {e}')
            except Exception as e:
                log.error(f'连接循环发生意外错误: {e}', exc_info=True)
            finally:
                # 5. 清理资源
                self.connected = False
                self._connection_event.clear()
                self._reset_response_subscription()
                self._fail_pending_requests()
                if self.client:
                    try:
                        self.client.disconnect()
                    finally:
                        self.client.loop_stop()
                    self.client = None

                # 6. 如果不是主动停止，则执行退避重连
                if not self._stop_event.is_set():
                    await self._handle_reconnect()

    async def _handle_reconnect(self) -> None:
        """执行指数退避重连。"""
        self.reconnect_attempts += 1
        if self.reconnect_attempts > self.config.max_reconnect_attempts:
            log.error(f'已达到最大重连尝试次数 ({self.config.max_reconnect_attempts})，停止重连。')
            self._stop_event.set()
            return

        # 指数退避计算
        delay = min(
            self.config.reconnect_interval * (2 ** min(self.reconnect_attempts - 1, 6)), self.config.backoff_max
        )
        # 添加抖动
        jitter = delay * self.config.backoff_jitter * random.uniform(-1, 1)
        delay = max(0, delay + jitter)

        log.warning(
            f'将在 {delay:.2f}s 后进行第 {self.reconnect_attempts}/{self.config.max_reconnect_attempts} 次重连尝试'
        )
        await asyncio.sleep(delay)

    async def _resubscribe_all(self) -> None:
        """重新订阅所有已注册的主题。"""
        if not self.client or not self.connected:
            return

        # 收集所有需要订阅的主题和 QoS。
        with self._callback_lock:
            topics_to_subscribe = [
                (subscription.topic, subscription.qos)
                for subscription in self.subscriptions.values()
            ]

        if not topics_to_subscribe:
            return

        # paho-mqtt 允许批量订阅
        try:
            result, _mid = self.client.subscribe(topics_to_subscribe)
            if result == mqtt.MQTT_ERR_SUCCESS:
                log.info(f'已批量重新订阅 {len(topics_to_subscribe)} 个主题。')
            else:
                log.error(f'批量重新订阅失败，错误码: {result}')
        except Exception as e:
            log.error(f'批量重新订阅过程中发生错误: {e}')

    # ------------------------------------------------------------------
    # 公共消息 API：订阅、取消订阅、发布、请求-响应。
    # ------------------------------------------------------------------
    async def subscribe(
            self,
            topic: str,
            callback: MessageCallback,
            qos: int = 1,
            shard_key_extractor: CallbackShardKeyExtractor | None = None,
    ) -> None:
        """
        订阅一个主题并注册回调函数。
        同一原始 Topic 重复注册时覆盖旧的回调、QoS 和分片键。
        """
        if not callable(callback):
            raise TypeError('callback 必须是可调用对象')
        qos = self._validate_qos(qos)

        async with self._client_lock:
            with self._callback_lock:
                # 1. 提取实际的主题过滤器
                actual_filter = self._extract_actual_filter(topic)

                subscription = MQTTSubscription(
                    topic=topic,
                    qos=qos,
                    callback=callback,
                    shard_key_extractor=shard_key_extractor,
                )
                self.subscriptions[topic] = subscription

                # 一个实际 filter 可能对应多个原始 Topic（例如不同共享订阅组）。
                matcher_subscriptions = self._matcher_subscriptions.setdefault(actual_filter, {})
                matcher_subscriptions[topic] = subscription
                self._matcher[actual_filter] = matcher_subscriptions

                # 3. 如果已连接，则执行 paho-mqtt 订阅
                if self.connected and self.client:
                    self.client.subscribe(topic, qos=qos)
                    log.info(f'已订阅主题: {topic} (QoS: {qos})')

    async def unsubscribe(self, topic: str) -> bool:
        """
        取消一个 Topic 的订阅。
        """
        async with self._client_lock:
            with self._callback_lock:
                subscription = self.subscriptions.pop(topic, None)
                if subscription is None:
                    log.warning(f'尝试取消订阅不存在的主题: {topic}')
                    return False

                actual_filter = self._extract_actual_filter(topic)
                matcher_subscriptions = self._matcher_subscriptions.get(actual_filter)
                if matcher_subscriptions is not None:
                    matcher_subscriptions.pop(topic, None)
                if not matcher_subscriptions:
                    self._matcher_subscriptions.pop(actual_filter, None)
                    try:
                        del self._matcher[actual_filter]
                    except KeyError:
                        pass

                if self.client and self.connected:
                    self.client.unsubscribe(topic)
                    log.info(f'已发送取消订阅请求: {topic}')

                return True

    async def publish(
            self,
            topic: str,
            payload: str | dict | bytes | None = None,
            qos: int = 1,
            retain: bool = False,
            properties: Properties | None = None,
            timeout: float | None = None,
    ) -> MQTTPublishResult:
        """发布消息到指定主题。"""
        qos = self._validate_qos(qos)
        if not self.connected or not self.client:
            log.warning(f'无法发布到 {topic}: 客户端未连接')
            return MQTTPublishResult(
                topic=topic,
                qos=qos,
                retain=retain,
                mid=None,
                published=False,
                error='mqtt client is not connected',
            )

        mid: int | None = None
        try:
            # 负载编码处理
            if payload is None:
                final_payload = None
            elif isinstance(payload, dict):
                final_payload = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            elif isinstance(payload, str):
                final_payload = payload.encode('utf-8')
            elif isinstance(payload, bytes):
                final_payload = payload
            else:
                # 尝试转换为字符串
                final_payload = str(payload).encode('utf-8')

            # Paho publish 本身是非阻塞的；发布确认由 on_publish 回调通知 asyncio Future。
            if properties is not None and self.config.version != MQTTVersion.V5:
                raise ValueError('MQTT properties require MQTTv5')
            info = self.client.publish(topic, final_payload, qos=qos, retain=retain, properties=properties)
            mid = info.mid

            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                error = mqtt.error_string(info.rc)
                log.error(f'发布到 {topic} 失败: rc={info.rc}, error={error}, mid={info.mid}')
                return MQTTPublishResult(
                    topic=topic,
                    qos=qos,
                    retain=retain,
                    mid=info.mid,
                    published=False,
                    error=error,
                )

            ack_future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
            self._pending_publishes[mid] = ack_future
            try:
                await asyncio.wait_for(
                    ack_future,
                    timeout=timeout if timeout is not None else self.config.unsubscribe_timeout,
                )
            finally:
                self._pending_publishes.pop(mid, None)

            # 回调到达后仍检查 Paho 的最终状态，避免把异常确认误判为发布成功。
            if not info.is_published():
                raise MQTTConnectionError('MQTT 发布确认已返回，但消息状态仍为未发布')

            log.debug(f'已发布消息到 {topic} (QoS: {qos}, Retain: {retain}, Mid: {info.mid})')
            return MQTTPublishResult(
                topic=topic,
                qos=qos,
                retain=retain,
                mid=info.mid,
                published=True,
            )
        except asyncio.TimeoutError:
            log.error(f'发布到 {topic} 超时: mid={mid}')
            return MQTTPublishResult(
                topic=topic,
                qos=qos,
                retain=retain,
                mid=mid,
                published=False,
                error='mqtt publish acknowledgement timeout',
            )
        except Exception as e:
            log.error(f'发布到 {topic} 失败: {e}', exc_info=True)
            return MQTTPublishResult(
                topic=topic,
                qos=qos,
                retain=retain,
                mid=mid,
                published=False,
                error=str(e),
            )

    async def request(
            self,
            topic: str,
            payload: str | dict | bytes | None = None,
            *,
            qos: int = 1,
            timeout: float = 10.0,
            retain: bool = False,
    ) -> MQTTMessageContext:
        """发布 MQTT 5 请求，并等待通过 Correlation Data 关联的响应。

        响应主题订阅在连接成功时建立；请求只负责创建唯一关联数据、发布带
        Response Topic 的消息，并在超时或响应完成后清理 pending Future。
        """
        if self.config.version != MQTTVersion.V5:
            raise ValueError('request() requires MQTTv5')
        if timeout <= 0:
            raise ValueError('timeout must be greater than zero')

        qos = self._validate_qos(qos)
        if not self.connected:
            raise MQTTConnectionError('mqtt client is not connected')
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        semaphore_acquired = False
        correlation_data: bytes | None = None

        def remaining_timeout() -> float:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError('mqtt request timed out')
            return remaining

        try:
            # 全局 pending 上限覆盖排队、发布和响应等待，避免高峰时 Future 无界增长。
            await asyncio.wait_for(self._request_semaphore.acquire(), timeout=remaining_timeout())
            semaphore_acquired = True

            # 先等待 SUBACK，确保设备的快速响应不会在响应主题订阅建立前丢失。
            await asyncio.wait_for(self._response_subscribed.wait(), timeout=remaining_timeout())

            correlation_data = uuid.uuid4().bytes
            response_future: asyncio.Future[MQTTMessageContext] = loop.create_future()
            self._pending_requests[correlation_data] = response_future

            # MQTT 5 标准请求-响应属性：设备应原样回传 CorrelationData。
            properties = Properties(PacketTypes.PUBLISH)
            properties.ResponseTopic = self._response_topic
            properties.CorrelationData = correlation_data

            result = await self.publish(
                topic=topic,
                payload=payload,
                qos=qos,
                retain=retain,
                properties=properties,
                timeout=remaining_timeout(),
            )
            if not result.published:
                if result.error == 'mqtt publish acknowledgement timeout':
                    raise TimeoutError(result.error)
                raise MQTTConnectionError(result.error or 'mqtt request publish failed')
            return await asyncio.wait_for(response_future, timeout=remaining_timeout())
        finally:
            # 无论成功、超时还是发布失败，都必须移除 Future，防止内存泄漏。
            if correlation_data is not None:
                self._pending_requests.pop(correlation_data, None)
            if semaphore_acquired:
                self._request_semaphore.release()

    # ------------------------------------------------------------------
    # 公共生命周期 API：断开连接和异步上下文管理。
    # ------------------------------------------------------------------
    async def disconnect(self) -> None:
        """优雅关闭连接。"""
        self._stop_event.set()
        self._reset_response_subscription()
        self._fail_pending_requests()
        async with self._client_lock:
            if self._connection_task and not self._connection_task.done():
                # 取消连接循环任务
                self._connection_task.cancel()
                try:
                    # 等待任务结束，给予清理时间
                    await asyncio.wait_for(self._connection_task, timeout=self.config.unsubscribe_timeout)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

            # 确保 client 被清理
            if self.client:
                try:
                    self.client.disconnect()
                finally:
                    self.client.loop_stop()
                self.client = None

            self.connected = False
            self._connection_task = None
            self._connection_event.clear()
            self._disconnect_event.clear()
            log.info('MQTT 客户端已断开连接')
        await self._shutdown_callback_workers()

    @asynccontextmanager
    async def context(self):
        """用作异步上下文管理器，确保连接和断开。"""
        try:
            connected = await self.connect()
            if not connected:
                raise MQTTConnectionError('无法连接到 MQTT Client')
            yield self
        finally:
            await self.disconnect()
