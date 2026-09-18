"""MQTT 3.1.1 服务端请求模拟：使用 payload 字段关联设备响应。"""

from __future__ import annotations

import json
import threading
import uuid
from typing import Any

import paho.mqtt.client as mqtt
from jose import jwt
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

MQTT_HOST = '120.92.21.75'
MQTT_PORT = 1883
MQTT_USERNAME = 'admin'
MQTT_JWT_SECRET = 'JiqidIoT_2016_CN'
MQTT_DEVICE_MODEL = 'js61'
MQTT_DEVICE_DID = 'TEST_DEVICE_DID'
RESPONSE_TIMEOUT = 10.0


class MQTTServerV311Service:
    """通过 response_topic 和 correlation_data 模拟 MQTT 3.1.1 请求-响应。"""

    def __init__(self) -> None:
        self.client_id = f'test-server-v311-{uuid.uuid4().hex}'
        self.request_topic = f'{MQTT_DEVICE_MODEL}/{MQTT_DEVICE_DID}/down/request'
        self.response_topic = f'fbapy/{self.client_id}/response'
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
            protocol=mqtt.MQTTv311,
        )
        self.client.on_connect = self._on_connect
        self.client.on_subscribe = self._on_subscribe
        self.client.on_message = self._on_message
        self.connected = threading.Event()
        self.subscribed = threading.Event()
        self.response_received = threading.Event()
        self.correlation_data: str | None = None
        self.response: dict[str, Any] | None = None

    def _on_connect(
            self, client: mqtt.Client, userdata: Any, flags: mqtt.ConnectFlags, reason_code: ReasonCode,
            properties: Properties | None = None,
    ) -> None:
        if reason_code.is_failure:
            print(f'MQTT 3.1.1 服务端连接失败: {reason_code}')
            return
        self.connected.set()
        client.subscribe(self.response_topic, qos=1)

    def _on_subscribe(
            self, client: mqtt.Client, userdata: Any, mid: int, reason_codes: list[ReasonCode],
            properties: Properties | None = None,
    ) -> None:
        if any(reason_code.is_failure for reason_code in reason_codes):
            print(f'MQTT 3.1.1 响应主题订阅失败: {reason_codes}')
            return
        self.subscribed.set()
        print(f'MQTT 3.1.1 服务端已订阅响应主题: {self.response_topic}')

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        response = json.loads(bytes(message.payload or b'{}').decode('utf-8'))
        if response.get('correlation_data') != self.correlation_data:
            print('忽略不属于当前请求的 MQTT 3.1.1 响应')
            return
        self.response = response
        self.response_received.set()

    def request(self) -> dict[str, Any]:
        """连接 Broker，订阅响应主题，发送请求并同步等待响应。"""
        password = jwt.encode(claims={}, key=MQTT_JWT_SECRET, algorithm='HS256')
        self.client.username_pw_set(MQTT_USERNAME, password)
        self.client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
        self.client.loop_start()
        try:
            if not self.connected.wait(RESPONSE_TIMEOUT):
                raise TimeoutError('MQTT 3.1.1 服务端连接超时')
            if not self.subscribed.wait(RESPONSE_TIMEOUT):
                raise TimeoutError('MQTT 3.1.1 响应主题订阅超时')

            request_id = uuid.uuid4().hex
            self.correlation_data = uuid.uuid4().hex
            payload = {
                'msg_id': request_id,
                'type': 'command',
                'service': 'system',
                'response_topic': self.response_topic,
                'correlation_data': self.correlation_data,
                'payload': {'action': 'ping', 'target': MQTT_DEVICE_DID, 'value': 'request-response-v311-test'},
            }
            info = self.client.publish(
                self.request_topic,
                json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                qos=1,
            )
            info.wait_for_publish(timeout=RESPONSE_TIMEOUT)
            print(f'MQTT 3.1.1 已发送请求: topic={self.request_topic}, msg_id={request_id}')
            if not self.response_received.wait(RESPONSE_TIMEOUT):
                raise TimeoutError('等待 MQTT 3.1.1 设备响应超时')
            return self.response or {}
        finally:
            self.client.disconnect()
            self.client.loop_stop()


def main() -> None:
    service = MQTTServerV311Service()
    response = service.request()
    print('收到 MQTT 3.1.1 设备响应:')
    print(json.dumps(response, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
