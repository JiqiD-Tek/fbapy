"""设备通用命令网关：只负责设备路由和 MQTT 请求-响应，不实现具体业务动作。"""

from __future__ import annotations

import json
import uuid
from typing import Any

from backend.common.exception import errors
from backend.common.mqtt import MQTTClient, MQTTMessageContext
from backend.utils.timezone import timezone


class DeviceGateway:
    """将统一的 service/action/payload 请求转发到构造时绑定的设备。"""

    def __init__(self, mqtt_client: MQTTClient, *, model: str, did: str) -> None:
        self._mqtt_client = mqtt_client
        self._did = did
        self._command_topic = f'{model}/{did}/down/command'
        self._request_topic = f'{model}/{did}/down/request'

    async def publish(
            self,
            *,
            service: str,
            action: str,
            payload: dict[str, Any],
            qos: int = 1,
    ) -> dict[str, Any]:
        """发布无需设备响应的命令；成功仅表示 MQTT 已确认发布，不表示设备已执行。"""
        message = {
            'msg_id': uuid.uuid4().hex,
            'timestamp': timezone.now().timestamp(),
            'service': service,
            'payload': {
                'action': action,
                **payload,
            },
        }
        try:
            await self._mqtt_client.publish(
                topic=self._command_topic,
                payload=message,
                qos=qos,
            )
        except TimeoutError as exc:
            raise errors.GatewayError(msg='MQTT 消息发布确认超时') from exc
        except Exception as exc:
            raise errors.GatewayError(msg=f'MQTT 消息发布失败: {exc}') from exc
        return {
            'request_id': message['msg_id'],
            'device_id': self._did,
            'success': True,
            'response': None,
            'topic': self._command_topic,
        }

    async def request(
            self,
            *,
            service: str,
            action: str,
            payload: dict[str, Any],
            timeout: float = 10.0,
    ) -> dict[str, Any]:
        """封装并发送一次设备请求，再将响应转换为可序列化字典。"""
        if timeout <= 0:
            raise ValueError('timeout 必须大于 0')

        message = {
            'msg_id': uuid.uuid4().hex,
            'timestamp': timezone.now().timestamp(),
            'service': service,
            'action': action,
            'payload': payload,
        }
        try:
            context: MQTTMessageContext = await self._mqtt_client.request(
                topic=self._request_topic,
                payload=message,
                timeout=timeout,
                qos=1,
            )
        except TimeoutError as exc:
            raise errors.GatewayError(msg='设备响应超时') from exc
        except Exception as exc:
            raise errors.GatewayError(msg=f'设备请求失败: {exc}') from exc

        try:
            decoded: Any = json.loads(context.payload.decode('utf-8')) if context.payload else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded = context.payload

        response_success = decoded.get('success', True) if isinstance(decoded, dict) else True
        return {
            'request_id': message['msg_id'],
            'device_id': self._did,
            'success': bool(response_success),
            'response': decoded,
            'topic': context.topic,
        }
