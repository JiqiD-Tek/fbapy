# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : messaging.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/12 20:25
"""

import json
import uuid

from backend.common.mqtt_broker import MQTTBroker
from backend.utils.timezone import timezone


class MessagingService:
    """
    设备消息服务类
    封装设备消息上行/下行逻辑
    业务化方法命名，便于扩展其他功能
    """

    def __init__(self, mqtt_client: MQTTBroker, did: str, model: str = 'k11') -> None:
        self.client = mqtt_client
        self.did = did
        self.model = model

    # ---------------- 公共方法 ----------------
    @staticmethod
    def _build_message(payload: dict, msg_type: str, service: str) -> dict:
        """
        构建通用消息结构
        :param payload: 业务 payload
        :param msg_type: 消息类型 report | command | log | ack | event
        :param service: 业务模块 system | feedback
        :return: 完整消息字典
        """
        return {
            'msg_id': str(uuid.uuid4().hex),
            'timestamp': timezone.now().timestamp(),
            'type': msg_type,
            'service': service,
            'payload': payload,
        }

    async def _publish(self, topic: str, message: dict) -> str:
        """
        发布消息到 MQTT
        :param topic: Topic 字符串
        :param message: 消息字典
        :return: msg_id
        """
        await self.client.publish(topic, json.dumps(message))
        return message['msg_id']

    # ---------------- 业务方法 ----------------
    async def send_request_log(self, feedback_id: int) -> str:
        """下发指令让设备上报日志"""
        payload = {
            'feedback_id': feedback_id,
        }
        topic = f'{self.model}/{self.did}/down/control'
        msg = self._build_message(payload, msg_type='command', service='feedback')
        return await self._publish(topic, msg)

    async def send_play_music(
            self, action: str, value: str, song: str, artist: str, playlist: str, platform: str, play_url: str = ''
    ) -> str:
        """下发点播音乐指令"""
        payload = {
            'action': action,  # 操作
            'value': value,  # 值
            'song': song,  # 音乐名称
            'artist': artist,  # 歌手名称
            'playlist': playlist,  # 歌单名称
            'platform': platform,  # 播放平台
            'play_url': play_url,  # 音乐地址
        }

        topic = f'{self.model}/{self.did}/down/control'
        msg = self._build_message(payload, msg_type='command', service='player')
        return await self._publish(topic, msg)

    async def send_system_control(self, target: str, action: str, value: str) -> str:
        """下发设备控制指令"""
        payload = {
            'action': action,
            'target': target,
            'value': value,
        }

        topic = f'{self.model}/{self.did}/down/control'
        msg = self._build_message(payload, msg_type='command', service='system')
        return await self._publish(topic, msg)

    async def send_alarm(self, action: str, target_time: str, message: str) -> str:
        """下发设备闹钟指令"""
        payload = {
            'action': action,
            'target_time': target_time,
            'message': message,
        }

        topic = f'{self.model}/{self.did}/down/control'
        msg = self._build_message(payload, msg_type='command', service='alarm')
        return await self._publish(topic, msg)
