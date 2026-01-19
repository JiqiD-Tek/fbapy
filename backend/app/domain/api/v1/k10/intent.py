# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : intent.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/13 16:05
"""

from fastapi import APIRouter, Depends

from backend.app.domain.service.messaging import MessagingService
from backend.common.mqtt_broker import get_mqtt, MQTTBroker
from backend.common.openai.core.openapi.weather_api import open_weather_map

from backend.common.response.response_schema import ResponseSchemaModel, response_base

from backend.app.domain.schema.intent import WeatherParam, MusicParam, AlarmParam, ControlParam

router = APIRouter()


@router.post('/weather', summary='天气查询')
async def weather_intent(
        obj: WeatherParam,
) -> ResponseSchemaModel[dict]:
    """天气查询"""
    data = await open_weather_map.get_weather_info(obj.city)
    return response_base.success(data=data)


@router.post('/music', summary='音乐操作')
async def music_intent(
        obj: MusicParam,
        mqtt_client: MQTTBroker = Depends(get_mqtt),
) -> ResponseSchemaModel[dict]:
    """音乐播放"""
    messaging_service = MessagingService(mqtt_client=mqtt_client, did=obj.did)
    await messaging_service.send_play_music(
        action=obj.action, value=obj.value, song=obj.song, artist=obj.artist, playlist=obj.playlist,
        platform=obj.platform)

    return response_base.success()


@router.post('/alarm', summary='闹钟设置')
async def alarm_intent(
        obj: AlarmParam,
        mqtt_client: MQTTBroker = Depends(get_mqtt),
) -> ResponseSchemaModel[dict]:
    messaging_service = MessagingService(mqtt_client=mqtt_client, did=obj.did)
    await messaging_service.send_alarm(action=obj.action, target_time=obj.target_time, message=obj.message)

    return response_base.success()


@router.post('/control', summary='设备控制')
async def control_intent(
        obj: ControlParam,
        mqtt_client: MQTTBroker = Depends(get_mqtt),
) -> ResponseSchemaModel[dict]:
    """设备控制"""
    messaging_service = MessagingService(mqtt_client=mqtt_client, did=obj.did)
    await messaging_service.send_system_control(target=obj.target, action=obj.action, value=obj.value)

    return response_base.success()
