# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : tool.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/13 16:05
"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends

from backend.app.cloud.schema.intent import WeatherParam
from backend.app.cloud.service.device.messaging import MessagingService
from backend.app.cloud.service.resource.weather import weather_service
from backend.common.mqtt_broker import MQTTBroker, get_mqtt
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
        mqtt_client: Annotated[MQTTBroker, Depends(get_mqtt)],
        did: Annotated[str, Body(description='设备did')],
        model: Annotated[str, Body(description='设备型号')],
        action: Annotated[str, Body(description='操作')],
        value: Annotated[str | None, Body(description='值')] = None,
        song: Annotated[str | None, Body(description='歌曲名称')] = None,
        artist: Annotated[str | None, Body(description='歌手名称')] = None,
        playlist: Annotated[str | None, Body(description='专辑名称')] = None,
        platform: Annotated[str | None, Body(description='播放平台')] = None,
        play_url: Annotated[str | None, Body(description='音频地址')] = None,
) -> ResponseModel:
    """音乐播放"""
    service = MessagingService(mqtt_client=mqtt_client, did=did, model=model)
    await service.send_play_music(
        action=action, value=value, song=song, artist=artist, playlist=playlist, platform=platform,
        play_url=play_url,
    )

    return response_base.success()


@router.post('/control', summary='设备控制')
async def control_tool(
        mqtt_client: Annotated[MQTTBroker, Depends(get_mqtt)],
        did: Annotated[str, Body(description='设备did')],
        model: Annotated[str, Body(description='设备型号')],
        action: Annotated[str, Body(description='动作')],
        target: Annotated[str, Body(description='目标')],
        value: Annotated[str | None, Body(description='值')] = None,
) -> ResponseModel:
    """设备控制"""
    service = MessagingService(mqtt_client=mqtt_client, did=did, model=model)
    await service.send_system_control(action=action, target=target, value=value)

    return response_base.success()


# P1
@router.post('/alarm', summary='闹钟设置')
async def alarm_tool(
        mqtt_client: Annotated[MQTTBroker, Depends(get_mqtt)],
        did: Annotated[str, Body(description='设备did')],
        model: Annotated[str, Body(description='设备型号')],
        action: Annotated[str, Body(description='操作')],
        target_time: Annotated[str | None, Body(description='时间')] = None,
        message: Annotated[str | None, Body(description='消息')] = None,
) -> ResponseModel:
    service = MessagingService(mqtt_client=mqtt_client, did=did, model=model)
    await service.send_alarm(action=action, target_time=target_time, message=message)

    return response_base.success()
