# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : messaging.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/12 20:25
"""
import asyncio

import json
import uuid
from typing import Dict

from backend.utils.timezone import timezone

from backend.common.mqtt_broker import MQTTBroker, get_mqtt


class MessagingService:
    """
    K10 设备消息服务类
    封装设备消息上行/下行逻辑
    业务化方法命名，便于扩展其他功能
    """

    def __init__(self, mqtt_client: MQTTBroker, did: str):
        self.client = mqtt_client
        self.did = did

    # ---------------- 公共方法 ----------------
    @staticmethod
    def _build_message(payload: Dict, msg_type: str, service: str) -> Dict:
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

    async def _publish(self, topic: str, message: Dict) -> str:
        """
        发布消息到 MQTT
        :param topic: Topic 字符串
        :param message: 消息字典
        :return: msg_id
        """
        await self.client.publish(topic, json.dumps(message))
        return message["msg_id"]

    # ---------------- 业务方法 ----------------
    async def send_request_log(self, store_url: str) -> str:
        """ 下发指令让设备上报日志 """
        payload = {
            "store_url": store_url,
        }
        topic = f"K10/{self.did}/down/control"
        msg = self._build_message(payload, msg_type="command", service="feedback")
        return await self._publish(topic, msg)

    async def send_play_music(self, query: str, album: str, song: str, singer: str, source: str = "wy") -> str:
        """ 下发点播音乐指令 """
        payload = {
            "query": query,
            "album": album,
            "song": song,
            "singer": singer,
            "source": source,
        }

        topic = f"K10/{self.did}/down/control"
        msg = self._build_message(payload, msg_type="command", service="player")
        return await self._publish(topic, msg)

    async def send_system_control(self, target: str, action: str, value: str) -> str:
        """ 下发设备控制指令 """
        payload = {
            "target": target,
            "action": action,
            "value": value,
        }

        topic = f"K10/{self.did}/down/control"
        msg = self._build_message(payload, msg_type="command", service="system")
        return await self._publish(topic, msg)
