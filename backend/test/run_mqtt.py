# -*- coding: UTF-8 -*-
"""
@Project : jiqidpy
@File    : run_mqtt.py
@Author  : guhua@jiqid.com
@Date    : 2025/09/22 11:21
"""

import asyncio
import time

from backend.common.log import log
from backend.common.mqtt_broker import MQTTMessageContext, close_mqtt, init_mqtt


async def main() -> None:
    """Example usage of AsyncMQTTManager."""

    client_id = 'D98BB367386B5B18A815EC31F74B43A6'
    mqtt = await init_mqtt()

    async def on_message(message_ctx: MQTTMessageContext) -> None:
        """全局消息处理回调示例。"""
        log.info(f'收到全局消息 | 主题: {message_ctx.topic} | 内容: {message_ctx.payload}')

    # 客户端订阅主题
    # await mqtt.subscribe(f'k11/{client_id}/down/control', on_message)

    # 发布消息
    for i in range(10):
        await mqtt.publish(
            f'k11/{client_id}/down/property', {'volume': 10 + i, 'timestamp': time.time(), 'device_id': client_id}
        )
        await asyncio.sleep(1)

    # 等待一段时间接收消息
    await asyncio.sleep(1000)

    await close_mqtt()


if __name__ == '__main__':
    asyncio.run(main())
