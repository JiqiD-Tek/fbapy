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
import time
import uuid

import paho.mqtt.client as mqtt

from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, Union, AsyncGenerator, Protocol
from collections.abc import Awaitable
from threading import Lock
from jose import jwt

from backend.common.log import log
from backend.core.conf import settings
from backend.utils.timezone import timezone


class MQTTVersion(Enum):
    V311 = mqtt.MQTTv311
    V5 = mqtt.MQTTv5


@dataclass
class MQTTConfig:
    host: str = settings.MQTT_HOST
    port: int = settings.MQTT_PORT
    username: Optional[str] = settings.MQTT_USERNAME
    password: Optional[str] = settings.MQTT_PASSWORD
    ssl: bool = False
    ssl_context: Any = None
    version: MQTTVersion = MQTTVersion.V5
    keepalive: int = 60
    clean_start: bool = True
    reconnect_interval: int = 5
    max_reconnect_attempts: int = 12
    client_id: Optional[str] = None
    backoff_max: int = 60
    backoff_jitter: float = 0.1
    unsubscribe_timeout: float = 5.0
    connection_timeout: float = 30.0


class MessageCallback(Protocol):
    def __call__(self, message_ctx: Dict[str, Any]) -> Union[None, Awaitable[None]]:
        ...


class MQTTConnectionError(Exception):
    """MQTT 连接失败的自定义异常。"""
    pass


class MQTTBroker:
    def __init__(self, config: MQTTConfig) -> None:
        self.config = config
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self.reconnect_attempts = 0
        self.subscriptions: Dict[str, Dict[int, MessageCallback]] = {}

        self._connection_event = asyncio.Event()
        self._disconnect_event = asyncio.Event()
        self._stop_event = asyncio.Event()

        self._client_lock = asyncio.Lock()
        self._callback_lock = Lock()
        self._connection_task: Optional[asyncio.Task] = None

        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self) -> bool:
        """连接 MQTT Broker。"""
        self._loop = asyncio.get_running_loop()

        async with self._client_lock:
            if self.connected:
                log.debug("已连接到 MQTT Broker")
                return True

            if self._connection_task and not self._connection_task.done():
                log.debug("连接任务已在进行中")
                try:
                    await asyncio.wait_for(
                        self._connection_task,
                        timeout=self.config.connection_timeout
                    )
                    return self.connected
                except asyncio.TimeoutError:
                    log.error(f"连接任务在 {self.config.connection_timeout}s 后超时")
                    return False
                except Exception as e:
                    log.error(f"连接任务发生意外错误: {str(e)}")
                    return False

            self._stop_event.clear()
            self._connection_event.clear()
            self._disconnect_event.clear()
            self._connection_task = self._loop.create_task(
                self._connection_loop(),
                name="mqtt_connection_loop"
            )

            try:
                await asyncio.wait_for(
                    self._connection_event.wait(),
                    timeout=self.config.connection_timeout
                )
                return self.connected
            except asyncio.TimeoutError:
                log.error(f"连接在 {self.config.connection_timeout}s 后超时")
                await self.disconnect()
                return False
            except Exception as e:
                log.error(f"连接过程中发生意外错误: {str(e)}")
                await self.disconnect()
                return False

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Dict, rc: int, *args) -> None:
        """客户端连接到 Broker 时的回调。"""
        with self._callback_lock:
            if rc == mqtt.CONNACK_ACCEPTED:
                self.connected = True
                self.reconnect_attempts = 0
                asyncio.run_coroutine_threadsafe(self._set_event(self._connection_event), self._loop)
                log.info(f"成功连接到 MQTT Broker {self.config.host}:{self.config.port}")
            else:
                log.error(f"连接失败，错误码 {rc}: {mqtt.connack_string(rc)}")
                self.connected = False
                asyncio.run_coroutine_threadsafe(self._clear_event(self._connection_event), self._loop)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int, *args) -> None:
        """客户端断开连接时的回调。"""
        with self._callback_lock:
            self.connected = False
            asyncio.run_coroutine_threadsafe(self._clear_event(self._connection_event), self._loop)
            # 触发断开事件，通知连接循环醒来
            asyncio.run_coroutine_threadsafe(self._set_event(self._disconnect_event), self._loop)
            if rc != mqtt.MQTT_ERR_SUCCESS:
                log.warning(f"意外断开连接，错误码: {rc}")

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        """接收到消息时的回调。"""
        topic = message.topic

        try:
            payload = message.payload.decode()
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                pass
        except Exception as e:
            log.error(f"解码消息负载失败 (主题: {topic}): {e}")
            return

        message_ctx = {
            'topic': topic,
            'payload': payload,
            'qos': message.qos,
            'retain': message.retain,
            'timestamp': timezone.now().timestamp(),
        }

        callbacks_to_run = []
        with self._callback_lock:
            for sub_topic, qos_callback in self.subscriptions.items():
                if self._topic_matches(sub_topic, topic):
                    callbacks_to_run.extend(qos_callback.values())

        def _invoke(_callback):
            try:
                coro = _callback(message_ctx)
                if asyncio.iscoroutine(coro):
                    asyncio.create_task(coro)
            except Exception as ex:
                log.error(f"识别结果回调: {ex}")

        for callback in callbacks_to_run:
            self._loop.call_soon_threadsafe(_invoke, callback)

    @staticmethod
    async def _set_event(event: asyncio.Event) -> None:
        event.set()

    @staticmethod
    async def _clear_event(event: asyncio.Event) -> None:
        event.clear()

    async def _connection_loop(self) -> None:
        """核心连接循环。"""
        while not self._stop_event.is_set():
            try:
                client_id = self.config.client_id or f"fbapy_{int(time.time_ns())}"
                log.info(f"正在尝试连接 MQTT Broker (ID: {client_id})")

                self.client = mqtt.Client(
                    client_id=client_id,
                    protocol=self.config.version.value,
                    userdata=None
                )
                self.client.on_connect = self._on_connect
                self.client.on_disconnect = self._on_disconnect
                self.client.on_message = self._on_message

                if self.config.username and self.config.password:
                    self.client.username_pw_set(self.config.username, self.config.password)

                if self.config.ssl:
                    self.client.tls_set_context(self.config.ssl_context)

                # 建立连接并启动后台循环
                self.client.connect(self.config.host, self.config.port, keepalive=self.config.keepalive)
                self.client.loop_start()

                # 等待连接成功
                await asyncio.wait_for(self._connection_event.wait(), timeout=self.config.connection_timeout)

                # 挂起协程，直到断开连接或外部停止
                self._disconnect_event.clear()
                await asyncio.wait(
                    [
                        self._loop.create_task(self._disconnect_event.wait()),
                        self._loop.create_task(self._stop_event.wait())
                    ],
                    return_when=asyncio.FIRST_COMPLETED
                )

            except asyncio.TimeoutError:
                log.error("MQTT 连接超时")
            except (OSError, ValueError) as e:
                log.error(f"MQTT 连接失败: {e}")
            except Exception as e:
                log.error(f"连接循环发生意外错误: {e}", exc_info=True)
            finally:
                self.connected = False
                if self.client:
                    self.client.loop_stop()
                    self.client.disconnect()
                    self.client = None

                # 如果不是主动停止，则执行退避重连
                if not self._stop_event.is_set():
                    await self._handle_reconnect()

    async def _handle_reconnect(self) -> None:
        """执行指数退避重连。"""
        if self.reconnect_attempts >= self.config.max_reconnect_attempts:
            log.error(f"已达到最大重连尝试次数 ({self.config.max_reconnect_attempts})")
            self._stop_event.set()
            return

        self.reconnect_attempts += 1
        delay = min(self.config.reconnect_interval * (2 ** min(self.reconnect_attempts, 6)),
                    self.config.backoff_max)
        jitter = delay * self.config.backoff_jitter * random.uniform(-1, 1)
        delay = max(0, delay + jitter)

        log.warning(
            f"将在 {delay:.2f}s 后进行第 {self.reconnect_attempts}/{self.config.max_reconnect_attempts} 次重连尝试")
        await asyncio.sleep(delay)

    async def _resubscribe_all(self) -> None:
        """重新订阅所有已注册的主题。"""
        if not self.client or not self.connected:
            return

        for topic, qos_callback in self.subscriptions.items():
            for qos in qos_callback.keys():
                try:
                    self.client.subscribe(topic, qos=qos)
                    log.debug(f"已重新订阅主题: {topic} (QoS: {qos})")
                except Exception as e:
                    log.error(f"重新订阅 {topic} 失败: {e}")

    @staticmethod
    def _topic_matches(subscription_topic: str, message_topic: str) -> bool:
        """判断 MQTT 消息主题是否匹配订阅主题。"""
        if subscription_topic.startswith('$share/'):
            parts = subscription_topic.split('/', 2)
            if len(parts) == 3:
                subscription_topic = parts[2]

        sub_segments = subscription_topic.split('/')
        msg_segments = message_topic.split('/')

        if '#' in sub_segments:
            if sub_segments[-1] != '#':
                return False
            idx = sub_segments.index('#')
            if len(msg_segments) < idx:
                return False
            return all(s == '+' or s == m for s, m in zip(sub_segments[:idx], msg_segments[:idx]))

        if len(sub_segments) != len(msg_segments):
            return False
        return all(s == '+' or s == m for s, m in zip(sub_segments, msg_segments))

    async def subscribe(self, topic: str, callback: Optional[MessageCallback], qos: int = 1) -> bool:
        try:
            async with self._client_lock:
                if topic not in self.subscriptions:
                    self.subscriptions[topic] = {}
                self.subscriptions[topic][qos] = callback

                if self.connected and self.client:
                    self.client.subscribe(topic, qos=qos)
                    log.info(f"已订阅主题: {topic} (QoS: {qos})")

                return True
        except Exception as e:
            log.error(f"订阅 {topic} 失败: {e}")
            return False

    async def unsubscribe(self, topic: str) -> bool:
        try:
            async with self._client_lock:
                if topic in self.subscriptions:
                    del self.subscriptions[topic]

                if self.client and self.connected:
                    self.client.unsubscribe(topic)
                    log.debug(f"已发送取消订阅请求: {topic}")
                return True
        except Exception as e:
            log.error(f"取消订阅 {topic} 失败: {e}")
            return False

    async def publish(self, topic: str, payload: Union[str, dict, bytes], qos: int = 1, retain: bool = False) -> bool:
        if not self.connected or not self.client:
            log.warning(f"无法发布到 {topic}: 客户端未连接")
            return False

        try:
            if not isinstance(payload, (str, bytes)):
                payload = json.dumps(payload, ensure_ascii=False)
            if isinstance(payload, str):
                payload = payload.encode()

            self.client.publish(topic, payload, qos=qos, retain=retain)
            log.debug(f"已发布消息到 {topic} (QoS: {qos}, Retain: {retain})")
            return True
        except Exception as e:
            log.error(f"发布到 {topic} 失败: {e}")
            return False

    async def disconnect(self) -> None:
        """优雅关闭连接。"""
        self._stop_event.set()
        async with self._client_lock:
            if self._connection_task and not self._connection_task.done():
                self._connection_task.cancel()
                try:
                    await asyncio.wait_for(self._connection_task, timeout=self.config.unsubscribe_timeout)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
                self.client = None

            self.connected = False
            self._connection_task = None
            await self._clear_event(self._connection_event)
            log.info("MQTT 客户端已断开连接")

    @asynccontextmanager
    async def context(self):
        try:
            connected = await self.connect()
            if not connected:
                raise MQTTConnectionError("无法连接到 MQTT Broker")
            yield self
        finally:
            await self.disconnect()

    def is_connected(self) -> bool:
        return self.connected


class MQTTDependency:
    _instance: Optional[MQTTBroker] = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_manager(cls, config: Optional[MQTTConfig] = None) -> MQTTBroker:
        """获取或创建单一的 MQTTBroker 实例。"""
        async with cls._lock:
            if cls._instance is None:
                config = config or await create_mqtt_config()
                cls._instance = MQTTBroker(config)
                connected = await cls._instance.connect()
                if not connected:
                    cls._instance = None
                    raise MQTTConnectionError("无法初始化 MQTT 管理器")
                await register_subscriptions(cls._instance)
            return cls._instance

    @classmethod
    async def close(cls) -> None:
        """关闭 MQTT 管理器"""
        async with cls._lock:
            if cls._instance:
                await cls._instance.disconnect()
                cls._instance = None
                log.info("MQTT 管理器已关闭")


async def create_mqtt_config(client_id: Optional[str] = None) -> MQTTConfig:
    """创建并验证 MQTT 配置。"""
    try:
        client_id = client_id or f"fbapy_{uuid.uuid4().hex}"

        # 服务器端认证
        username = settings.MQTT_USERNAME
        password = jwt.encode(claims={"model": "K10"}, key=settings.MQTT_JWT_SECRET, algorithm="HS256")

        # 设备认证
        # username = "C4:1C:9C:09:C9:81"
        # password = "FFCE1FC24AFE5283AF39564CCB1559F5"

        return MQTTConfig(
            host=settings.MQTT_HOST,
            port=settings.MQTT_PORT,
            username=username,
            password=password,
            client_id=client_id,
            connection_timeout=getattr(settings, 'MQTT_CONNECTION_TIMEOUT', 30.0)
        )
    except AttributeError as e:
        log.error(f"缺少 MQTT 配置项: {str(e)}")
        raise MQTTConnectionError(f"无效的 MQTT 配置: {str(e)}")


async def register_subscriptions(manager: MQTTBroker) -> None:
    for topic in settings.MQTT_UP_TOPICS:
        await manager.subscribe(topic, on_message)
        log.debug(f"已注册全局订阅: {topic}")


async def init_mqtt(config: Optional[MQTTConfig] = None) -> MQTTBroker:
    return await MQTTDependency.get_manager(config)


async def close_mqtt() -> None:
    await MQTTDependency.close()


async def get_mqtt(config: Optional[MQTTConfig] = None) -> AsyncGenerator[MQTTBroker, None]:
    """FastAPI 依赖注入。"""
    manager = await MQTTDependency.get_manager(config)
    yield manager


async def on_message(message_ctx: Dict[str, Any]) -> None:
    log.info(f"收到全局消息 | 主题: {message_ctx['topic']} | 内容: {message_ctx['payload']}")
