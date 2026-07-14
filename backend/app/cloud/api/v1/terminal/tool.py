# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : tool.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/13 16:05
"""

from fastapi import APIRouter

from backend.app.cloud.schema.intent import AlarmToolParam, ControlToolParam, MusicToolParam, WeatherParam
from backend.app.cloud.service.device.messaging import MessagingService
from backend.app.cloud.service.resource.providers.weather import weather_service
from backend.common.mqtt_broker import MQTTDependency
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base

router = APIRouter()


# P0
@router.post('/weather', summary='天气查询')
async def weather_tool(
        obj: WeatherParam,
) -> ResponseSchemaModel[dict]:
    """天气查询"""
    data = await weather_service.query(city=obj.city, ip=obj.ip)

    return response_base.success(data=data)


@router.post('/music', summary='音乐操作')
async def music_tool(
        obj: MusicToolParam,
) -> ResponseModel:
    """音乐播放"""
    mqtt_client = await MQTTDependency.get_manager()
    service = MessagingService(mqtt_client=mqtt_client, did=obj.did, model=obj.model)
    await service.send_play_music(
        action=obj.action,
        value=obj.value,
        song=obj.song,
        artist=obj.artist,
        playlist=obj.playlist,
        platform=obj.platform,
        play_url=obj.play_url,
    )

    return response_base.success()


@router.post('/control', summary='设备控制')
async def control_tool(
        obj: ControlToolParam,
) -> ResponseModel:
    """设备控制"""
    mqtt_client = await MQTTDependency.get_manager()
    service = MessagingService(mqtt_client=mqtt_client, did=obj.did, model=obj.model)
    await service.send_system_control(action=obj.action, target=obj.target, value=obj.value)

    return response_base.success()


# P1
@router.post('/alarm', summary='闹钟设置')
async def alarm_tool(
        obj: AlarmToolParam,
) -> ResponseModel:
    mqtt_client = await MQTTDependency.get_manager()
    service = MessagingService(mqtt_client=mqtt_client, did=obj.did, model=obj.model)
    await service.send_alarm(action=obj.action, target_time=obj.target_time, message=obj.message)

    return response_base.success()
