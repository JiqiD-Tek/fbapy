"""MQTT 客户端的应用生命周期和单例依赖管理。"""

from __future__ import annotations

import asyncio
import uuid

from jose import jwt

from backend.common.log import log
from backend.common.mqtt.client import MQTTClient
from backend.common.mqtt.types import MQTTConfig, MQTTConnectionError
from backend.core.conf import settings


class MQTTDependency:
    """FastAPI/应用生命周期使用的 MQTTClient 单例管理器。"""

    _instance: MQTTClient | None = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_manager(cls, config: MQTTConfig | None = None) -> MQTTClient:
        """获取或创建单一的 MQTTClient 实例。"""
        async with cls._lock:
            if cls._instance is None:
                client = MQTTClient(config or create_mqtt_config())
                if not await client.connect():
                    await client.disconnect()
                    raise MQTTConnectionError('无法初始化 MQTT 管理器：连接失败')
                cls._instance = client
            return cls._instance

    @classmethod
    async def close(cls) -> None:
        """关闭 MQTT 管理器。"""
        async with cls._lock:
            if cls._instance is not None:
                await cls._instance.disconnect()
                cls._instance = None
                log.info('MQTT 管理器已关闭')


def create_mqtt_config(client_id: str | None = None) -> MQTTConfig:
    """从应用配置创建 MQTT 客户端配置。"""
    try:
        password = jwt.encode(claims={}, key=settings.MQTT_JWT_SECRET, algorithm='HS256')
        return MQTTConfig(
            host=settings.MQTT_HOST,
            port=settings.MQTT_PORT,
            username=settings.MQTT_USERNAME,
            password=password,
            client_id=client_id or f'fbapy_{uuid.uuid4().hex}',
            connection_timeout=30.0,
        )
    except AttributeError as exc:
        log.error(f'缺少 MQTT 配置项: {exc}')
        raise MQTTConnectionError(f'无效的 MQTT 配置: {exc}') from exc


async def init_mqtt(config: MQTTConfig | None = None) -> MQTTClient:
    """初始化并返回 MQTT 客户端实例。"""
    return await MQTTDependency.get_manager(config)


async def close_mqtt() -> None:
    """关闭 MQTT 客户端实例。"""
    await MQTTDependency.close()
