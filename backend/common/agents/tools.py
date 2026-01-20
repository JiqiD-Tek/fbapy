# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : tools.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/20 09:44
"""
from backend.common.log import log
from backend.common.agents.api_clients.weather_api import open_weather_map

from backend.common.agents.core.llm.tool_context import function_tool


@function_tool()
async def get_weather(
        city: str
):
    """
    Retrieve current weather information for a given city.

    IMPORTANT:
    - The 'city' parameter MUST be in English.
    - If the user provides a city name in any other language (e.g., "北京", "Москва"),
      you MUST translate it to English before processing.

    Returns:
        A short text summary of the weather, or an error message if
        the request fails.
    """

    log.info(f"[get_weather] Retrieving weather for English city name: {city}")
    try:
        return await open_weather_map.get_weather_info(city)
    except Exception as e:
        log.error(f"[get_weather] Exception for {city}: {e}")
        return f"I'm sorry, an error occurred while retrieving the weather for {city}."
