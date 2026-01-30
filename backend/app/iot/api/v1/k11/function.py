# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : function.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/13 16:05
"""

from fastapi import APIRouter, Depends

from backend.app.iot.service.messaging import MessagingService
from backend.common.mqtt_broker import get_mqtt, MQTTBroker
from backend.app.live.agents.api_clients.weather_api import open_weather_map

from backend.common.response.response_schema import ResponseSchemaModel, response_base, ResponseModel

from backend.app.iot.schema.intent import WeatherParam, MusicParam, AlarmParam, ControlParam

router = APIRouter()


# P0
@router.post('/weather', summary='天气查询')
async def weather_function(
        obj: WeatherParam,
) -> ResponseSchemaModel[dict]:
    """天气查询"""
    data = await open_weather_map.get_weather_info(obj.city)

    return response_base.success(data=data)


@router.post('/music', summary='音乐操作')
async def music_function(
        obj: MusicParam,
        mqtt_client: MQTTBroker = Depends(get_mqtt),
) -> ResponseModel:
    """音乐播放"""
    messaging_service = MessagingService(mqtt_client=mqtt_client, did=obj.did)
    await messaging_service.send_play_music(
        action=obj.action, value=obj.value, song=obj.song, artist=obj.artist, playlist=obj.playlist,
        platform=obj.platform)

    return response_base.success()


@router.post('/control', summary='设备控制')
async def control_function(
        obj: ControlParam,
        mqtt_client: MQTTBroker = Depends(get_mqtt),
) -> ResponseModel:
    """设备控制"""
    messaging_service = MessagingService(mqtt_client=mqtt_client, did=obj.did)
    await messaging_service.send_system_control(target=obj.target, action=obj.action, value=obj.value)

    return response_base.success()


# P1
@router.post('/alarm', summary='闹钟设置')
async def alarm_function(
        obj: AlarmParam,
        mqtt_client: MQTTBroker = Depends(get_mqtt),
) -> ResponseModel:
    messaging_service = MessagingService(mqtt_client=mqtt_client, did=obj.did)
    await messaging_service.send_alarm(action=obj.action, target_time=obj.target_time, message=obj.message)

    return response_base.success()
