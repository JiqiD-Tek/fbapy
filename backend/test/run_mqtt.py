# -*- coding: UTF-8 -*-
"""
@Project : jiqidpy
@File    : run_mqtt.py
@Author  : guhua@jiqid.com
@Date    : 2025/09/22 11:21
"""
import asyncio
import time
from typing import Dict, Any

from backend.common.mqtt_broker import init_mqtt, close_mqtt
from backend.common.log import log


async def main():
    """Example usage of AsyncMQTTManager."""

    client_id = "jqd000000001"
    mqtt = await init_mqtt()

    async def on_message(message_ctx: Dict[str, Any]) -> None:
        log.info(f"Received on {message_ctx['topic']}: {message_ctx['payload']}")

    # 客户端订阅主题
    # await mqtt.subscribe(f"oh2g/topic/{client_id}", on_message)

    # 发布消息
    for i in range(10):
        await mqtt.publish(f"K10/{client_id}/up/property", {
            "volume": 10 + i,
            "timestamp": time.time(),
            "device_id": client_id
        })
        await asyncio.sleep(1)

    # 等待一段时间接收消息
    await asyncio.sleep(10)

    await close_mqtt()


if __name__ == '__main__':
    asyncio.run(main())
