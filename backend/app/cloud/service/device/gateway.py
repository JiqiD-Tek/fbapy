"""设备通用命令网关：只负责设备路由和 MQTT 请求-响应，不实现具体业务动作。"""

from __future__ import annotations

import json
import uuid
from typing import Any

from backend.common.exception import errors
from backend.common.mqtt import MQTTClient, MQTTMessageContext
from backend.utils.timezone import timezone


class DeviceGateway:
    """将统一的 service/action/payload 请求转发到指定设备。"""

    def __init__(self, mqtt_client: MQTTClient) -> None:
        self.client = mqtt_client

    async def publish_message(self, *, model: str, did: str, message: dict[str, Any], qos: int = 1) -> str:
        """发布已经封装好的设备消息，返回业务消息 ID。"""
        result = await self.client.publish(
            topic=f'{model}/{did}/down/command',
            payload=message,
            qos=qos,
        )
        if not result.published:
            raise errors.ServerError(msg=f'MQTT publish failed: {result.error or "unknown error"}')
        return str(message.get('msg_id', ''))

    async def publish_command(
            self,
            *,
            model: str,
            did: str,
            service: str,
            action: str,
            payload: dict[str, Any],
            qos: int = 1,
    ) -> str:
        """封装并发布通用 command 消息，供业务服务复用。"""
        message = {
            'msg_id': uuid.uuid4().hex,
            'timestamp': timezone.now().timestamp(),
            'service': service,
            'payload': {
                'action': action,
                **payload,
            },
        }
        return await self.publish_message(model=model, did=did, message=message, qos=qos)

    async def request(
            self,
            *,
            model: str,
            did: str,
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
            context: MQTTMessageContext = await self.client.request(
                # down/request 专用于需要响应的请求；无需响应的命令固定使用 down/command。
                topic=f'{model}/{did}/down/request',
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
            'device_id': did,
            'success': bool(response_success),
            'response': decoded,
            'topic': context.topic,
        }
