# -*- coding: UTF-8 -*-
"""
@Project : jiqidpy
@File    : mqtt_broker.py
@Author  : guhua@jiqid.com
@Date    : 2025/09/12 11:22
"""

import asyncio
import json
import random
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, Union, AsyncGenerator, Protocol
from collections.abc import Awaitable
from threading import Lock

import paho.mqtt.client as mqtt
from jose import jwt
from backend.common.log import log
from backend.core.conf import settings


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
    """Custom exception for MQTT connection failures."""
    pass


class MQTTBroker:
    def __init__(self, config: MQTTConfig) -> None:
        self.config = config
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self.reconnect_attempts = 0
        self.subscriptions: Dict[str, Dict[int, MessageCallback]] = {}
        self._message_task: Optional[asyncio.Task] = None
        self._connection_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        self._client_lock = asyncio.Lock()
        self._callback_lock = Lock()

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._connection_task: Optional[asyncio.Task] = None

    @property
    def loop(self):
        """Lazy initialization of event loop"""
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
        return self._loop

    async def connect(self) -> bool:
        async with self._client_lock:
            if self.connected:
                log.debug("Already connected to MQTT broker")
                return True

            if self._connection_task and not self._connection_task.done():
                log.debug("Connection already in progress")
                try:
                    await asyncio.wait_for(
                        self._connection_task,
                        timeout=self.config.connection_timeout
                    )
                    return self.connected
                except asyncio.TimeoutError:
                    log.error(f"Connection task timeout after {self.config.connection_timeout}s")
                    return False
                except Exception as e:
                    log.error(f"Unexpected error in connection task: {str(e)}")
                    return False

            self._stop_event.clear()
            self._connection_event.clear()
            self._connection_task = self.loop.create_task(
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
                log.error(f"Connection timeout after {self.config.connection_timeout}s")
                await self.disconnect()
                return False
            except Exception as e:
                log.error(f"Unexpected error during connection: {str(e)}")
                await self.disconnect()
                return False

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Dict, rc: int, *args) -> None:
        """Callback for when the client connects to the broker."""
        with self._callback_lock:
            if rc == mqtt.CONNACK_ACCEPTED:
                self.connected = True
                self.reconnect_attempts = 0
                # Schedule event setting on the asyncio loop
                asyncio.run_coroutine_threadsafe(self._set_connection_event(), self.loop)
                log.info(f"Connected to MQTT broker {self.config.host}:{self.config.port}")
                asyncio.run_coroutine_threadsafe(self._resubscribe_all(), self.loop)
            else:
                log.error(f"Connection failed with code {rc}: {mqtt.connack_string(rc)}")
                self.connected = False
                asyncio.run_coroutine_threadsafe(self._clear_connection_event(), self.loop)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int, *args) -> None:
        """Callback for when the client disconnects."""
        with self._callback_lock:
            self.connected = False
            asyncio.run_coroutine_threadsafe(self._clear_connection_event(), self.loop)
            if rc != mqtt.MQTT_ERR_SUCCESS:
                log.warning(f"Unexpected disconnect with code {rc}")
                asyncio.run_coroutine_threadsafe(self._handle_reconnect(), self.loop)

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        """Callback for when a message is received."""
        topic = message.topic
        with self._callback_lock:
            for sub_topic, qos_callback in self.subscriptions.items():
                if self._topic_matches(sub_topic, topic):
                    for callback in qos_callback.values():
                        try:
                            payload = message.payload.decode()
                            try:
                                payload = json.loads(payload)
                            except json.JSONDecodeError:
                                pass

                            message_ctx = {
                                'topic': topic,
                                'payload': payload,
                                'qos': message.qos,
                                'retain': message.retain,
                                'timestamp': time.time()
                            }

                            if asyncio.iscoroutinefunction(callback):
                                asyncio.run_coroutine_threadsafe(callback(message_ctx), self.loop)
                            else:
                                self.loop.call_soon_threadsafe(callback, message_ctx)
                        except Exception as e:
                            log.error(f"Error processing message on {topic} for subscription {sub_topic}: {str(e)}")

    async def _set_connection_event(self) -> None:
        """Helper to set connection event in the asyncio loop."""
        self._connection_event.set()

    async def _clear_connection_event(self) -> None:
        """Helper to clear connection event in the asyncio loop."""
        self._connection_event.clear()

    async def _connection_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                client_id = self.config.client_id or f"jiqidpy_{int(time.time_ns())}"
                log.info(f"Connecting to MQTT broker {self.config.host}:{self.config.port} (client_id: {client_id})")

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

                if self.config.version == MQTTVersion.V5 and self.config.clean_start:
                    self.client._clean_start = True

                self.client.connect(
                    self.config.host,
                    self.config.port,
                    keepalive=self.config.keepalive
                )
                self.client.loop_start()

                # Wait for connection event
                await asyncio.wait_for(
                    self._connection_event.wait(),
                    timeout=self.config.connection_timeout
                )

                # Process messages in a separate task
                if not self._message_task or self._message_task.done():
                    self._message_task = self.loop.create_task(
                        self._process_messages_forever(),
                        name="mqtt_message_processor"
                    )

                # Keep the connection alive
                while self.connected and not self._stop_event.is_set():
                    await asyncio.sleep(1)

            except (OSError, ValueError) as e:
                log.error(f"MQTT connection failed: {str(e)}")
                self.connected = False
                await self._clear_connection_event()
                await self._handle_reconnect()
            except Exception as e:
                log.error(f"Unexpected error in connection loop: {str(e)}")
                self.connected = False
                await self._clear_connection_event()
                await self._handle_reconnect()
            finally:
                if self.client:
                    self.client.loop_stop()
                    self.client.disconnect()
                    self.client = None

    async def _handle_reconnect(self) -> None:
        if self.reconnect_attempts >= self.config.max_reconnect_attempts:
            log.error(f"Maximum reconnection attempts ({self.config.max_reconnect_attempts}) reached")
            self._stop_event.set()
            return

        self.reconnect_attempts += 1
        delay = min(self.config.reconnect_interval * (2 ** min(self.reconnect_attempts, 6)),
                    self.config.backoff_max)
        jitter = delay * self.config.backoff_jitter * random.uniform(-1, 1)
        delay = max(0, delay + jitter)

        log.warning(
            f"Reconnection attempt {self.reconnect_attempts}/{self.config.max_reconnect_attempts} in {delay:.2f}s")
        await asyncio.sleep(delay)

    async def _resubscribe_all(self) -> None:
        if not self.client or not self.connected:
            log.warning("Cannot resubscribe: client not connected")
            return

        for topic, qos_callback in self.subscriptions.items():
            for qos in qos_callback.keys():
                try:
                    self.client.subscribe(topic, qos=qos)
                    log.debug(f"Resubscribed to topic: {topic} with QoS: {qos}")
                except (OSError, ValueError) as e:
                    log.error(f"Failed to resubscribe to {topic}: {str(e)}")

    async def _process_messages_forever(self) -> None:
        # paho-mqtt handles message processing in its own loop
        while self.connected and not self._stop_event.is_set():
            await asyncio.sleep(1)

    def _topic_matches(self, subscription_topic: str, message_topic: str) -> bool:
        # 处理共享订阅主题：去掉 $share/group/ 前缀
        if subscription_topic.startswith('$share/'):
            # 提取共享订阅后的实际主题
            parts = subscription_topic.split('/')
            if len(parts) >= 3:
                # 从 $share/group/actual/topic 中提取 actual/topic
                actual_topic = '/'.join(parts[2:])
                subscription_topic = actual_topic

        # 原有的匹配逻辑
        def match_segment(sub_seg: str, msg_seg: str) -> bool:
            if sub_seg == '+' or sub_seg == '#':
                return True
            return sub_seg == msg_seg

        sub_segments = subscription_topic.split('/')
        msg_segments = message_topic.split('/')

        if '#' in sub_segments:
            idx = sub_segments.index('#')
            return len(msg_segments) >= idx and all(
                match_segment(sub_segments[i], msg_segments[i]) for i in range(idx)
            )

        if len(sub_segments) != len(msg_segments):
            return False

        return all(match_segment(sub, msg) for sub, msg in zip(sub_segments, msg_segments))

    async def subscribe(self, topic: str, callback: Optional[MessageCallback], qos: int = 1) -> bool:
        try:
            async with self._client_lock:
                if topic not in self.subscriptions:
                    self.subscriptions[topic] = {}
                self.subscriptions[topic][qos] = callback

                if self.connected and self.client:
                    try:
                        self.client.subscribe(topic, qos=qos)
                        log.info(f"Subscribed to topic: {topic} with QoS: {qos}")
                    except (OSError, ValueError) as e:
                        log.error(f"Failed to subscribe to {topic}: {str(e)}")
                        return False

                log.info(f"Registered subscription for topic: {topic}")
                return True
        except Exception as e:
            log.error(f"Failed to subscribe to {topic}: {str(e)}")
            return False

    async def unsubscribe(self, topic: str) -> bool:
        try:
            async with self._client_lock:
                if topic in self.subscriptions:
                    del self.subscriptions[topic]
                    log.info(f"Unsubscribed from topic: {topic}")

                if self.client and self.connected:
                    try:
                        self.client.unsubscribe(topic)
                        log.debug(f"MQTT unsubscribe sent for topic: {topic}")
                    except (OSError, ValueError) as e:
                        log.warning(f"Failed to send MQTT unsubscribe for {topic}: {str(e)}")

                return True
        except Exception as e:
            log.error(f"Failed to unsubscribe from {topic}: {str(e)}")
            return False

    async def publish(self, topic: str, payload: Union[str, dict, bytes], qos: int = 1, retain: bool = False) -> bool:
        if not self.connected or not self.client:
            log.warning(f"Cannot publish to {topic}: client not connected")
            return False

        try:
            if not isinstance(payload, (str, bytes)):
                payload = json.dumps(payload, ensure_ascii=False)
            if isinstance(payload, str):
                payload = payload.encode()

            self.client.publish(topic, payload, qos=qos, retain=retain)
            log.debug(f"Published message to {topic} (QoS: {qos}, retain: {retain})")
            return True
        except (OSError, ValueError) as e:
            log.error(f"Failed to publish to {topic}: {str(e)}")
            return False
        except Exception as e:
            log.error(f"Unexpected error publishing to {topic}: {str(e)}")
            return False

    async def disconnect(self) -> None:
        self._stop_event.set()
        async with self._client_lock:
            tasks_to_cancel = []
            if self._connection_task and not self._connection_task.done():
                tasks_to_cancel.append(self._connection_task)
            if self._message_task and not self._message_task.done():
                tasks_to_cancel.append(self._message_task)

            for task in tasks_to_cancel:
                task.cancel()

            if tasks_to_cancel:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*tasks_to_cancel, return_exceptions=True),
                        timeout=self.config.unsubscribe_timeout
                    )
                except asyncio.TimeoutError:
                    log.warning("Timeout waiting for tasks to cancel")

            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
                self.client = None

            self.connected = False
            self._message_task = None
            self._connection_task = None
            await self._clear_connection_event()
            log.info("MQTT client disconnected")

    @asynccontextmanager
    async def context(self):
        try:
            connected = await self.connect()
            if not connected:
                raise MQTTConnectionError("Failed to connect to MQTT broker")
            yield self
        finally:
            await self.disconnect()

    def is_connected(self) -> bool:
        return self.connected

    async def wait_for_connection(self, timeout: float = 30.0) -> bool:
        try:
            await asyncio.wait_for(self._connection_event.wait(), timeout=timeout)
            return self.connected
        except asyncio.TimeoutError:
            log.warning(f"Connection timeout after {timeout}s")
            return False


class MQTTDependency:
    _instance: Optional[MQTTBroker] = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_manager(cls, config: Optional[MQTTConfig] = None) -> MQTTBroker:
        """获取或创建单一的 AsyncMQTTManager 实例"""
        async with cls._lock:
            if cls._instance is None:
                config = config or await create_mqtt_config()
                cls._instance = MQTTBroker(config)
                connected = await cls._instance.connect()
                if not connected:
                    cls._instance = None
                    raise MQTTConnectionError("Failed to initialize MQTT manager")
                await register_global_subscriptions(cls._instance)
            return cls._instance

    @classmethod
    async def close(cls) -> None:
        """关闭 MQTT 管理器"""
        async with cls._lock:
            if cls._instance:
                await cls._instance.disconnect()
                cls._instance = None
                log.info("MQTT manager closed")


async def create_mqtt_config(client_id: Optional[str] = None) -> MQTTConfig:
    """创建 MQTT 配置并验证设置"""
    try:
        client_id = client_id or f"jiqidpy_{int(time.time_ns())}"
        password = jwt.encode(claims={"model": "oh2g"}, key=settings.MQTT_JWT_SECRET, algorithm="HS256")

        return MQTTConfig(
            host=settings.MQTT_HOST,
            port=settings.MQTT_PORT,
            username=settings.MQTT_USERNAME,
            password=settings.MQTT_PASSWORD,
            client_id=client_id,
            connection_timeout=getattr(settings, 'MQTT_CONNECTION_TIMEOUT', 30.0)
        )
    except AttributeError as e:
        log.error(f"缺少 MQTT 配置: {str(e)}")
        raise MQTTConnectionError(f"无效的 MQTT 配置: {str(e)}")


async def register_global_subscriptions(manager: MQTTBroker) -> None:
    """注册全局 MQTT 订阅"""

    async def on_message(message_ctx: Dict[str, Any]) -> None:
        log.info(f"接收到消息，主题: {message_ctx['topic']}，内容: {message_ctx['payload']}")

    system_topic = getattr(settings, 'MQTT_SYSTEM_TOPIC', None)
    if system_topic:
        await manager.subscribe(system_topic, on_message)
        log.debug(f"注册全局订阅主题: {system_topic}")
    else:
        log.warning("未定义 MQTT_SYSTEM_TOPIC，跳过全局订阅")


async def init_mqtt(config: Optional[MQTTConfig] = None) -> MQTTBroker:
    """初始化 MQTT 连接并注册全局订阅"""
    return await MQTTDependency.get_manager(config)


async def close_mqtt() -> None:
    """优雅关闭 MQTT 连接"""
    await MQTTDependency.close()


async def get_mqtt(config: Optional[MQTTConfig] = None) -> AsyncGenerator[MQTTBroker, None]:
    """为 FastAPI 提供 MQTT 管理器依赖"""
    manager = await MQTTDependency.get_manager(config)
    yield manager
