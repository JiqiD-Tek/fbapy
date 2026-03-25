# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : function.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/13 16:05
"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends

from backend.app.iot.schema.intent import WeatherParam
from backend.app.iot.service.device.messaging import MessagingService
from backend.app.live.agents.api_clients.weather_api import open_weather_map
from backend.common.mqtt_broker import MQTTBroker, get_mqtt
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base

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
    mqtt_client: Annotated[MQTTBroker, Depends(get_mqtt)],
    did: Annotated[str, Body(description='设备did')],
    action: Annotated[str, Body(description='操作')],
    value: Annotated[str | None, Body(description='值')] = None,
    song: Annotated[str | None, Body(description='歌曲名称')] = None,
    artist: Annotated[str | None, Body(description='歌手名称')] = None,
    playlist: Annotated[str | None, Body(description='专辑名称')] = None,
    platform: Annotated[str | None, Body(description='播放平台')] = None,
) -> ResponseModel:
    """音乐播放"""
    messaging_service = MessagingService(mqtt_client=mqtt_client, did=did)
    await messaging_service.send_play_music(
        action=action, value=value, song=song, artist=artist, playlist=playlist, platform=platform
    )

    return response_base.success()


@router.post('/control', summary='设备控制')
async def control_function(
    mqtt_client: Annotated[MQTTBroker, Depends(get_mqtt)],
    did: Annotated[str, Body(description='设备did')],
    target: Annotated[str, Body(description='目标')],
    action: Annotated[str, Body(description='动作')],
    value: Annotated[str | None, Body(description='值')] = None,
) -> ResponseModel:
    """设备控制"""
    messaging_service = MessagingService(mqtt_client=mqtt_client, did=did)
    await messaging_service.send_system_control(target=target, action=action, value=value)

    return response_base.success()


# P1
@router.post('/alarm', summary='闹钟设置')
async def alarm_function(
    mqtt_client: Annotated[MQTTBroker, Depends(get_mqtt)],
    did: Annotated[str, Body(description='设备did')],
    action: Annotated[str, Body(description='操作')],
    target_time: Annotated[str | None, Body(description='时间')] = None,
    message: Annotated[str | None, Body(description='消息')] = None,
) -> ResponseModel:
    messaging_service = MessagingService(mqtt_client=mqtt_client, did=did)
    await messaging_service.send_alarm(action=action, target_time=target_time, message=message)

    return response_base.success()
