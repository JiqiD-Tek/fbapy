# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : messaging.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/12 20:25
"""

import json
import uuid
from typing import Dict

from backend.utils.timezone import timezone
from backend.common.mqtt_broker import MQTTBroker


class MessagingService:
    """
    K10 设备消息服务类
    封装设备消息上行/下行逻辑
    业务化方法命名，便于扩展其他功能
    """

    def __init__(self, mqtt_client: MQTTBroker, device_id: int):
        """
        :param mqtt_client: paho-mqtt 或其他 MQTT 客户端实例
        :param device_id: 设备 ID
        """
        self.client = mqtt_client
        self.device_id = device_id

    # ---------------- 公共方法 ----------------
    def _build_message(self, payload: Dict, msg_type: str, service: str) -> Dict:
        """
        构建通用消息结构
        :param payload: 业务 payload
        :param msg_type: 消息类型 report | command | log | ack | event
        :param service: 业务模块 system | feedback
        :return: 完整消息字典
        """
        return {
            "msg_id": str(uuid.uuid4().hex),
            "timestamp": timezone.now().timestamp(),
            "type": msg_type,
            "service": service,
            "payload": payload
        }

    def _publish(self, topic: str, message: Dict) -> str:
        """
        发布消息到 MQTT
        :param topic: Topic 字符串
        :param message: 消息字典
        :return: msg_id
        """
        self.client.publish(topic, json.dumps(message))
        return message["msg_id"]

    # ---------------- 业务方法 ----------------
    def send_request_log(self, store_url: str) -> str:
        """ 下发指令让设备上报日志 """
        payload = {
            "action": "report_log",
            "params": {
                "store_url": store_url,
            }
        }
        topic = f"k10/{self.device_id}/down/control"
        msg = self._build_message(payload, msg_type="command", service="feedback")
        return self._publish(topic, msg)
