"""MQTT 5 设备端请求-响应模拟服务。"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections import OrderedDict
from typing import Any

import paho.mqtt.client as mqtt
from jose import jwt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

MQTT_HOST = '120.92.21.75'
MQTT_PORT = 1883
MQTT_USERNAME = 'admin'
MQTT_JWT_SECRET = 'JiqidIoT_2016_CN'
MQTT_DEVICE_MODEL = 'js61'
MQTT_DEVICE_DID = 'TEST_DEVICE_DID'


class MQTTDeviceV5Service:
    """使用 MQTT 5 Response Topic 和 Correlation Data 模拟设备。"""

    def __init__(self) -> None:
        self.request_topic = f'{MQTT_DEVICE_MODEL}/{MQTT_DEVICE_DID}/down/request'
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f'test-device-v5-{uuid.uuid4().hex}',
            protocol=mqtt.MQTTv5,
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.received = threading.Event()
        # 缓存最近请求的业务响应，重复 msg_id 只重发响应，不重复执行设备动作。
        self._response_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._response_cache_maxsize = 1000

    def _on_connect(
            self, client: mqtt.Client, userdata: Any, flags: mqtt.ConnectFlags, reason_code: ReasonCode,
            properties: Properties | None = None,
    ) -> None:
        if not reason_code.is_failure:
            client.subscribe(self.request_topic, qos=1)
            print(f'MQTT 5 设备已订阅: {self.request_topic}')

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        request = json.loads(bytes(message.payload or b'{}').decode('utf-8'))
        properties = getattr(message, 'properties', None)
        response_topic = getattr(properties, 'ResponseTopic', None)
        correlation_data = getattr(properties, 'CorrelationData', None)
        if not response_topic or not correlation_data:
            print('MQTT 5 请求缺少 Response Topic 或 Correlation Data')
            return

        msg_id = request.get('msg_id')
        if not isinstance(msg_id, str) or not msg_id:
            print('MQTT 5 请求缺少 msg_id，无法保证幂等')
            return

        response = self._response_cache.get(msg_id)
        if response is None:
            # 真实设备应在这里执行一次业务动作，再缓存最终结果。
            response = {
                'type': 'response',
                'success': True,
                'msg_id': msg_id,
                'payload': {'accepted': True},
            }
            self._response_cache[msg_id] = response
            if len(self._response_cache) > self._response_cache_maxsize:
                self._response_cache.popitem(last=False)
        else:
            self._response_cache.move_to_end(msg_id)
            print(f'MQTT 5 收到重复请求，直接返回缓存响应: msg_id={msg_id}')

        response_properties = Properties(PacketTypes.PUBLISH)
        response_properties.CorrelationData = correlation_data
        client.publish(
            response_topic,
            json.dumps(response, ensure_ascii=False).encode('utf-8'),
            qos=1,
            properties=response_properties,
        )
        self.received.set()
        print(f'MQTT 5 已响应: topic={response_topic}, msg_id={msg_id}')

    def start(self) -> None:
        password = jwt.encode(claims={}, key=MQTT_JWT_SECRET, algorithm='HS256')
        self.client.username_pw_set(MQTT_USERNAME, password)
        self.client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
        self.client.loop_start()

    def stop(self) -> None:
        try:
            self.client.disconnect()
        finally:
            self.client.loop_stop()


def main() -> None:
    service = MQTTDeviceV5Service()
    try:
        service.start()
        print(f'MQTT 5 设备模拟服务已启动: {service.request_topic}')
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('正在停止 MQTT 5 设备模拟服务...')
    finally:
        service.stop()


if __name__ == '__main__':
    main()
