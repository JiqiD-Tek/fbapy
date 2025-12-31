# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : tst_action_weather.py
@Author  : guhua@jiqid.com
@Date    : 2025/05/28 19:55
"""
import re
from typing import Optional, List, Literal, Dict

from backend.common.log import log
from backend.common.openapi.amap.amap_client import amap_client
from backend.common.openapi.weather.open_weather_map import open_weather_map
from backend.common.device.repository import DeviceStateRepository

from backend.common.openai.llm.intention.action.base import Action, timed_execute, ActionResult


class ActionWeather(Action):
    """天气查询工具（支持实时数据口语化播报）"""
    name = "weather"

    def __init__(self):
        self.api = open_weather_map
        self.amap = amap_client

    @property
    def system_prompt(self) -> str:
        return """Weather Report Prompt Template

        Data Guidelines:
        - Use raw API data only; do not infer or supplement missing data.
        - Mark missing data as "Not available".
        - Units: Temperature in Celsius ("low to high", e.g., "10 to 25 degrees"), wind speed in levels (e.g., "Level 3 to 4"), wind direction in cardinal terms (e.g., "Northeast wind").

        Report Template:
        {Location} {Date} Weather Report:
        - Temperature: {Temperature}
        - Condition: {Weather Condition}
        - Wind: Level {Wind Speed} {Wind Direction}
        Tip: {Life Advice}

        Error Handling:
        - Missing Data: "Unable to retrieve {Missing Data} for {Location}. Please try again later."
        - Extreme Weather: "Warning: {Alert Content}. Recommended: {Protective Measures}."

        Prohibited Actions:
        - Using raw API terms (e.g., "moderate rain").
        - Mentioning specific times (e.g., "14:30").
        - Including unverified advice or calculation formulas.
        """

    @timed_execute(threshold_ms=1000)
    async def process(
            self, text: str, content: str,
            conversation_history: Optional[List[Dict[Literal["user", "assistant"], str]]] = None,
            device_repo: DeviceStateRepository = None,
            **kwargs
    ) -> ActionResult:
        """ content=南京 """
        log.debug(f"获取天气位置: {content}")

        weather = await self._get_weather_info(content=content, device_repo=device_repo)

        return ActionResult(
            user_prompt=f"""
                Current time: {self.en_formatted_date}
                Input: {text}
                Weather API data: {weather}
                Generate a relevant response considering:
                - Previous conversation history
                - Related data
            """
        )

    async def _get_weather_info(self, content: str = "", device_repo: DeviceStateRepository = None) -> str:
        """获取天气信息（优化版）
        """
        # 定义默认错误消息
        default_error_msg = "Unable to obtain weather information temporarily"
        location_error_msg = "City information not obtained, weather information temporarily unavailable"

        # 如果用户提供了有效城市名称
        if content and content != "unknown":
            try:
                if self.is_english(content):
                    return await self.api.get_weather_info(query=content)
                return await self.amap.get_weather_info(query=content)
            except Exception as e:
                log.error(f"获取天气信息失败，错误信息：{e}")
                return default_error_msg

        # 尝试通过IP获取位置
        if device_repo is None:
            return location_error_msg

        try:
            # 通过IP获取城市信息
            ip = await device_repo.get_field("ip")
            location = await self.amap.get_location_by_ip(ip=ip)
            if not location or not location.get("city"):
                log.debug(f"无法通过IP获取城市信息: {ip}")
                return location_error_msg

            # 获取该城市天气
            return await self.amap.get_weather_info(query=location["city"])
        except Exception as e:
            log.error(f"获取天气信息失败，错误信息：{e}")
            return default_error_msg

    @classmethod
    def is_english(cls, string):
        """ 检查字符串是否主要为英文字符 """
        pattern = re.compile(r'^[A-Za-z0-9\s,.!?;:"\'()\[\]{}]+$')
        return bool(pattern.fullmatch(string))
