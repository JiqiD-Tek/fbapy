"""MQTT 5 服务端请求模拟：发送请求并接收设备响应。"""

from __future__ import annotations

import asyncio
import json
import uuid

from jose import jwt

from backend.common.mqtt import MQTTConfig, MQTTVersion, close_mqtt, init_mqtt

MQTT_HOST = '120.92.21.75'
MQTT_PORT = 1883
MQTT_USERNAME = 'admin'
MQTT_JWT_SECRET = 'JiqidIoT_2016_CN'
MQTT_DEVICE_MODEL = 'js61'
MQTT_DEVICE_DID = 'TEST_DEVICE_DID'


async def main() -> None:
    """连接 MQTT Broker，发送一次控制请求并打印设备响应。"""
    password = jwt.encode(claims={}, key=MQTT_JWT_SECRET, algorithm='HS256')
    broker = await init_mqtt(MQTTConfig(
        host=MQTT_HOST,
        port=MQTT_PORT,
        username=MQTT_USERNAME,
        password=password,
        version=MQTTVersion.V5,
        client_id=f'test-server-{uuid.uuid4().hex}',
    ))
    try:
        request_id = uuid.uuid4().hex
        topic = f'{MQTT_DEVICE_MODEL}/{MQTT_DEVICE_DID}/down/request'
        payload = {
            'msg_id': request_id,
            'timestamp': 0,
            'type': 'command',
            'service': 'system',
            'payload': {'action': 'ping', 'target': MQTT_DEVICE_DID, 'value': 'request-response-test'},
        }
        print(f'正在发送请求: topic={topic}, msg_id={request_id}')
        response = await broker.request(topic=topic, payload=payload, timeout=10)
        print(f'收到响应: topic={response.topic}')
        print(f'Correlation Data: {response.correlation_data!r}')
        try:
            print(json.dumps(json.loads(response.payload.decode('utf-8')), ensure_ascii=False, indent=2))
        except (UnicodeDecodeError, json.JSONDecodeError):
            print(response.payload)
    finally:
        await close_mqtt()


if __name__ == '__main__':
    asyncio.run(main())
