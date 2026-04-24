# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : mqtt_broker.py
@Author  : guhua@jiqid.com
@Date    : 2025/09/12 11:22
"""

import asyncio
import json
import random
import uuid

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any

import paho.mqtt.client as mqtt

from jose import jwt
from paho.mqtt.matcher import MQTTMatcher

from backend.app.cloud.timeseries.event_store import EventStore
from backend.common.log import log
from backend.core.conf import settings
from backend.utils.timezone import timezone


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
    password: str | None = field(default_factory=lambda: settings.MQTT_PASSWORD)
    ssl: bool = False
    ssl_context: Any = None
    version: MQTTVersion = MQTTVersion.V5
    keepalive: int = 60
    clean_start: bool = True
    reconnect_interval: int = 5  # 初始重连间隔 (秒)
    max_reconnect_attempts: int = 12  # 最大重连尝试次数
    client_id: str | None = None
    backoff_max: int = 60  # 指数退避最大延迟 (秒)
    backoff_jitter: float = 0.1  # 退避抖动比例
    unsubscribe_timeout: float = 5.0  # 取消订阅/断开连接等待超时
    connection_timeout: float = 30.0  # 连接等待超时


@dataclass
class MQTTMessageContext:
    """MQTT 消息上下文。"""

    topic: str
    payload: Any
    qos: int
    retain: bool
    timestamp: float


# 消息回调函数类型定义
MessageCallback = Callable[[MQTTMessageContext], None | Awaitable[None]]


class MQTTConnectionError(Exception):
    """MQTT 连接失败的自定义异常。"""


class MQTTBroker:
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

        # 存储订阅信息，key: 原始 topic (str, 可能包含 $share/)
        # value: {callback_id: MessageCallback}
        self.subscriptions: dict[str, dict[int, MessageCallback]] = {}
        # 记录每个 topic 下 callback 的 qos
        self._subscriptions_qos: dict[str, dict[int, int]] = {}
        # MQTTMatcher 存储的是实际的 topic filter (不含 $share/group/)
        # key: actual_filter (str), value: {callback_id: MessageCallback}
        self._matcher = MQTTMatcher()
        self._matcher_callbacks: dict[str, dict[int, MessageCallback]] = {}
        self._callback_id_counter = 0

        # 异步事件用于控制连接循环
        self._connection_event = asyncio.Event()  # 连接成功时设置
        self._disconnect_event = asyncio.Event()  # 意外断开时设置
        self._stop_event = asyncio.Event()  # 外部请求停止时设置

        # 锁
        self._client_lock = asyncio.Lock()  # 保护 client 对象的创建/销毁和连接/断开操作
        self._callback_lock = Lock()  # 保护 self.subscriptions 和 self._matcher，被 paho-mqtt 线程访问

        self._connection_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self) -> bool:
        """
        连接 MQTT Broker。
        如果已连接，则直接返回 True。
        如果连接任务正在进行，则等待其完成。
        """
        self._loop = asyncio.get_running_loop()

        async with self._client_lock:
            if self.connected:
                log.debug('已连接到 MQTT Broker')
                return True

            if self._connection_task and not self._connection_task.done():
                log.debug('连接任务已在进行中，等待连接事件...')
            else:
                # 启动新的连接循环
                self._stop_event.clear()
                self._connection_event.clear()
                self._disconnect_event.clear()
                self._connection_task = self._loop.create_task(self._connection_loop(), name='mqtt_connection_loop')

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

    def _on_connect(
            self, client: mqtt.Client, userdata: Any, flags: dict, rc: int, properties: mqtt.Properties | None = None
    ) -> None:
        """客户端连接到 Broker 时的回调。"""
        with self._callback_lock:
            if rc == mqtt.CONNACK_ACCEPTED:
                self.connected = True
                self.reconnect_attempts = 0
                # 成功连接后，重新订阅所有主题
                self._submit_coroutine_threadsafe(self._resubscribe_all())
                # 设置连接事件，唤醒等待 connect() 的协程
                self._call_loop_threadsafe(self._connection_event.set)
                log.info(f'成功连接到 MQTT Broker {self.config.host}:{self.config.port}')
            else:
                log.error(f'连接失败，错误码 {rc}: {mqtt.connack_string(rc)}')
                self.connected = False
                # 清除连接事件，确保 connect() 失败
                self._call_loop_threadsafe(self._connection_event.clear)

    def _on_disconnect(
            self, client: mqtt.Client, userdata: Any, rc: int, properties: mqtt.Properties | None = None
    ) -> None:
        """客户端断开连接时的回调。"""
        with self._callback_lock:
            self.connected = False
            # 清除连接事件
            self._call_loop_threadsafe(self._connection_event.clear)
            # 触发断开事件，通知连接循环醒来
            self._call_loop_threadsafe(self._disconnect_event.set)
            if rc != mqtt.MQTT_ERR_SUCCESS:
                log.warning(f'意外断开连接，错误码: {rc}')

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        """接收到消息时的回调。"""
        topic = message.topic

        # 1. 解码消息负载
        try:
            payload_bytes = message.payload
            if payload_bytes:
                payload_str = payload_bytes.decode('utf-8')
                try:
                    payload = json.loads(payload_str)
                except json.JSONDecodeError:
                    payload = payload_str  # 非 JSON 格式，保持为字符串
            else:
                payload = None
        except Exception as e:
            log.error(f'解码消息负载失败 (主题: {topic}): {e}')
            return

        message_ctx = MQTTMessageContext(
            topic=topic,
            payload=payload,
            qos=message.qos,
            retain=message.retain,
            timestamp=timezone.now().timestamp(),
        )

        # 2. 查找匹配的回调函数
        callbacks_to_run = []
        with self._callback_lock:
            # 使用 MQTTMatcher 查找所有匹配该主题的订阅回调
            # iter_match(topic) 会返回所有匹配该 topic 的过滤器所关联的值
            for callbacks in self._matcher.iter_match(topic):
                if isinstance(callbacks, dict):
                    callbacks_to_run.extend(callbacks.values())

        # 3. 在主事件循环中调用回调
        def _invoke(_callback: MessageCallback) -> None:
            """在主线程中执行回调，并处理协程。"""
            try:
                coro = _callback(message_ctx)
                if asyncio.iscoroutine(coro):
                    # 如果是协程，创建任务在主循环中执行
                    asyncio.create_task(coro)
            except Exception as ex:
                log.error(f'消息回调执行失败: {ex}', exc_info=True)

        for callback in callbacks_to_run:
            # 使用 call_soon_threadsafe 将执行安排到主事件循环
            self._call_loop_threadsafe(_invoke, callback)

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
    def _max_qos(qos_map: dict[int, int], default: int = 1) -> int:
        """获取回调集合中的最大 QoS。"""
        return max(qos_map.values(), default=default)

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
                log.info(f'正在尝试连接 MQTT Broker (ID: {self._client_id})')

                self.client = mqtt.Client(client_id=self._client_id, protocol=self.config.version.value)
                self.client.on_connect = self._on_connect
                self.client.on_disconnect = self._on_disconnect
                self.client.on_message = self._on_message

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
                _, pending = await asyncio.wait(
                    {disconnect_task, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
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

        # 收集所有需要订阅的主题和 QoS
        topics_to_subscribe = []
        with self._callback_lock:
            for topic, callbacks in self.subscriptions.items():
                if callbacks:
                    # 重新订阅时，使用原始的 topic 字符串（可能包含 $share/）和最高 QoS
                    # 找到该主题下所有回调中最高的 QoS
                    max_qos = self._max_qos(self._subscriptions_qos.get(topic, {}), default=1)
                    topics_to_subscribe.append((topic, max_qos))

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

    async def subscribe(self, topic: str, callback: MessageCallback, qos: int = 1) -> int:
        """
        订阅一个主题并注册回调函数。
        返回一个用于取消订阅的 callback_id。
        """
        if not callable(callback):
            raise TypeError('callback 必须是可调用对象')
        qos = self._validate_qos(qos)

        async with self._client_lock:
            with self._callback_lock:
                self._callback_id_counter += 1
                callback_id = self._callback_id_counter

                # 1. 提取实际的主题过滤器
                actual_filter = self._extract_actual_filter(topic)

                # 2. 更新内部订阅状态
                topic_callbacks = self.subscriptions.setdefault(topic, {})
                topic_qos_map = self._subscriptions_qos.setdefault(topic, {})
                topic_callbacks[callback_id] = callback
                topic_qos_map[callback_id] = qos

                # 使用独立的 matcher 存储，避免不同 topic 共享同一 actual_filter 时互相覆盖
                matcher_callbacks = self._matcher_callbacks.get(actual_filter)
                if matcher_callbacks is None:
                    matcher_callbacks = {}
                    self._matcher_callbacks[actual_filter] = matcher_callbacks
                    self._matcher[actual_filter] = matcher_callbacks
                matcher_callbacks[callback_id] = callback

                # 3. 如果已连接，则执行 paho-mqtt 订阅
                if self.connected and self.client:
                    topic_max_qos = self._max_qos(topic_qos_map, default=qos)
                    self.client.subscribe(topic, qos=topic_max_qos)
                    log.info(f'已订阅主题: {topic} (QoS: {topic_max_qos})')

                return callback_id

    async def unsubscribe(self, topic: str, callback_id: int | None = None) -> bool:
        """
        取消订阅一个主题或移除一个回调函数。
        如果提供了 callback_id，则只移除该回调。
        如果未提供 callback_id，则移除该主题下的所有回调，并取消 paho-mqtt 订阅。
        """
        async with self._client_lock:
            with self._callback_lock:
                topic_callbacks = self.subscriptions.get(topic)
                if not topic_callbacks:
                    log.warning(f'尝试取消订阅不存在的主题: {topic}')
                    return False

                actual_filter = self._extract_actual_filter(topic)
                topic_qos_map = self._subscriptions_qos.setdefault(topic, {})
                matcher_callbacks = self._matcher_callbacks.get(actual_filter)

                if callback_id is not None:
                    # 移除单个回调
                    if callback_id not in topic_callbacks:
                        log.warning(f'主题 {topic} 下不存在回调 ID: {callback_id}')
                        return False

                    previous_qos = self._max_qos(topic_qos_map, default=1)
                    del topic_callbacks[callback_id]
                    topic_qos_map.pop(callback_id, None)
                    if matcher_callbacks is not None:
                        matcher_callbacks.pop(callback_id, None)
                    log.debug(f'已移除主题 {topic} 的回调 ID: {callback_id}')

                # 检查是否还有其他回调
                should_unsubscribe_topic = callback_id is None or not topic_callbacks

                if callback_id is None:
                    callback_ids = list(topic_callbacks)
                    for callback_key in callback_ids:
                        if matcher_callbacks is not None:
                            matcher_callbacks.pop(callback_key, None)
                    topic_callbacks.clear()
                    topic_qos_map.clear()

                if should_unsubscribe_topic:
                    self.subscriptions.pop(topic, None)
                    self._subscriptions_qos.pop(topic, None)
                elif callback_id is not None:
                    new_qos = self._max_qos(topic_qos_map, default=previous_qos)
                else:
                    new_qos = None

                if matcher_callbacks is not None and not matcher_callbacks:
                    self._matcher_callbacks.pop(actual_filter, None)
                    if actual_filter in self._matcher:
                        del self._matcher[actual_filter]

                if self.client and self.connected:
                    if should_unsubscribe_topic:
                        self.client.unsubscribe(topic)
                        log.info(f'已发送取消订阅请求: {topic}')
                    elif callback_id is not None:
                        # 主题仍有回调时同步 QoS，确保后续消息等级符合当前最大 QoS
                        self.client.subscribe(topic, qos=new_qos)
                        log.debug(f'已更新主题 {topic} 的订阅 QoS: {new_qos}')

                return True

    async def publish(
            self, topic: str, payload: str | dict | bytes | None = None, qos: int = 1, retain: bool = False
    ) -> bool:
        """发布消息到指定主题。"""
        qos = self._validate_qos(qos)
        if not self.connected or not self.client:
            log.warning(f'无法发布到 {topic}: 客户端未连接')
            return False

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

            # paho-mqtt 的 publish 是非阻塞的
            info = self.client.publish(topic, final_payload, qos=qos, retain=retain)

            # 可以选择等待消息发送完成，但通常不需要
            # info.wait_for_publish()

            log.debug(f'已发布消息到 {topic} (QoS: {qos}, Retain: {retain}, Mid: {info.mid})')
            return True
        except Exception as e:
            log.error(f'发布到 {topic} 失败: {e}', exc_info=True)
            return False

    async def disconnect(self) -> None:
        """优雅关闭连接。"""
        self._stop_event.set()
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

    @asynccontextmanager
    async def context(self):
        """用作异步上下文管理器，确保连接和断开。"""
        try:
            connected = await self.connect()
            if not connected:
                raise MQTTConnectionError('无法连接到 MQTT Broker')
            yield self
        finally:
            await self.disconnect()


class MQTTDependency:
    """
    FastAPI/依赖注入的 MQTT Broker 单例管理器。
    """

    _instance: MQTTBroker | None = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_manager(cls, config: MQTTConfig | None = None) -> MQTTBroker:
        """获取或创建单一的 MQTTBroker 实例。"""
        async with cls._lock:
            if cls._instance is None:
                # 1. 创建配置
                config = config or create_mqtt_config()

                # 2. 创建实例
                cls._instance = MQTTBroker(config)

                # 3. 尝试连接
                connected = await cls._instance.connect()
                if not connected:
                    cls._instance = None
                    raise MQTTConnectionError('无法初始化 MQTT 管理器：连接失败')

                # 4. 注册全局订阅
                await register_subscriptions(cls._instance)
            return cls._instance

    @classmethod
    async def close(cls) -> None:
        """关闭 MQTT 管理器"""
        async with cls._lock:
            if cls._instance:
                await cls._instance.disconnect()
                cls._instance = None
                log.info('MQTT 管理器已关闭')


def create_mqtt_config(client_id: str | None = None) -> MQTTConfig:
    """创建并验证 MQTT 配置。"""
    try:
        client_id = client_id or f'fbapy_{uuid.uuid4().hex}'

        username = "3E:96:10:BA:61:2F"
        password = "D98BB367386B5B18A815EC31F74B43A6"

        # 服务器端认证：使用 JWT 编码密码
        username = settings.MQTT_USERNAME
        password = jwt.encode(claims={}, key=settings.MQTT_JWT_SECRET, algorithm='HS256')

        return MQTTConfig(
            host=settings.MQTT_HOST,
            port=settings.MQTT_PORT,
            username=username,
            password=password,
            client_id=client_id,
            connection_timeout=30.0,
        )
    except AttributeError as e:
        log.error(f'缺少 MQTT 配置项: {e}')
        raise MQTTConnectionError(f'无效的 MQTT 配置: {e}')


async def register_subscriptions(manager: MQTTBroker) -> None:
    """注册应用启动时的全局订阅。"""
    # 假设 settings.MQTT_UP_TOPICS 和 on_message 存在
    for topic in settings.MQTT_UP_TOPICS:
        # 订阅时不需要关心返回的 callback_id，因为这是全局订阅
        await manager.subscribe(topic, on_message)
        log.debug(f'已注册全局订阅: {topic}')


async def init_mqtt(config: MQTTConfig | None = None) -> MQTTBroker:
    """初始化并返回 MQTT Broker 实例。"""
    return await MQTTDependency.get_manager(config)


async def close_mqtt() -> None:
    """关闭 MQTT Broker 实例。"""
    await MQTTDependency.close()


async def get_mqtt(config: MQTTConfig | None = None) -> AsyncGenerator[MQTTBroker, None]:
    """FastAPI 依赖注入函数。"""
    manager = await MQTTDependency.get_manager(config)
    yield manager


async def on_message(message_ctx: MQTTMessageContext) -> None:
    """全局消息处理回调示例。"""
    log.debug(f'收到全局消息 | 主题: {message_ctx.topic} | 内容: {message_ctx.payload}')
    try:
        await EventStore.insert(message_ctx)
    except Exception as e:
        log.debug(f'保存消息失败: {e}', exc_info=True)
