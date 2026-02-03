# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : function.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/13 16:05
"""
from typing import Optional

from fastapi import APIRouter, Depends, Body

from backend.app.iot.service.messaging import MessagingService
from backend.common.mqtt_broker import get_mqtt, MQTTBroker
from backend.app.live.agents.api_clients.weather_api import open_weather_map

from backend.common.response.response_schema import ResponseSchemaModel, response_base, ResponseModel

from backend.app.iot.schema.intent import WeatherParam

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
        mqtt_client: MQTTBroker = Depends(get_mqtt),
        did: str = Body(..., description='设备did'),
        action: str = Body(..., description='操作'),
        value: Optional[str] = Body(None, description='值'),
        song: Optional[str] = Body(None, description='歌曲名称'),
        artist: Optional[str] = Body(None, description='歌手名称'),
        playlist: Optional[str] = Body(None, description='专辑名称'),
        platform: Optional[str] = Body(None, description='播放平台'),
) -> ResponseModel:
    """音乐播放"""
    messaging_service = MessagingService(mqtt_client=mqtt_client, did=did)
    await messaging_service.send_play_music(
        action=action, value=value, song=song, artist=artist, playlist=playlist,
        platform=platform)

    return response_base.success()


@router.post('/control', summary='设备控制')
async def control_function(
        mqtt_client: MQTTBroker = Depends(get_mqtt),
        did: str = Body(..., description='设备did'),
        target: str = Body(..., description='目标'),
        action: str = Body(..., description='动作'),
        value: Optional[str] = Body(None, description='值'),
) -> ResponseModel:
    """设备控制"""
    messaging_service = MessagingService(mqtt_client=mqtt_client, did=did)
    await messaging_service.send_system_control(target=target, action=action, value=value)

    return response_base.success()


# P1
@router.post('/alarm', summary='闹钟设置')
async def alarm_function(
        mqtt_client: MQTTBroker = Depends(get_mqtt),
        did: str = Body(..., description='设备did'),
        action: str = Body(..., description='操作'),
        target_time: Optional[str] = Body(None, description='时间'),
        message: Optional[str] = Body(None, description='消息'),
) -> ResponseModel:
    messaging_service = MessagingService(mqtt_client=mqtt_client, did=did)
    await messaging_service.send_alarm(action=action, target_time=target_time, message=message)

    return response_base.success()
