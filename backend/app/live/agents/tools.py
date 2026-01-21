# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : tools.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/20 09:44
"""
from datetime import timedelta

from backend.common.log import log
from backend.utils.timezone import TimeZone
from backend.app.live.agents.api_clients.weather_api import open_weather_map
from backend.app.live.agents.core.llm.tool_context import function_tool


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


@function_tool()
async def set_alarm_at(
        target_time: str,
        message: str = "Time to wake up!"
) -> str:
    """
    Schedule a reminder or alarm at a specific date and time.

    This function is intended for absolute time alarms, e.g.,
    "Wake me up tomorrow at 08:00".

    Args:
        target_time: The target datetime in 'YYYY-MM-DD HH:MM:SS' format (local time).
        message: The reminder message to announce when the alarm triggers.

    Returns:
        A confirmation message indicating the alarm has been set,
        or an error message if the time format is invalid or in the past.
    """

    try:
        now = TimeZone().now()
        target_dt = TimeZone().from_str(target_time)
        if (target_dt - now).total_seconds() <= 0:
            return "The alarm time must be in the future."

        log.info(f"[set_alarm] Alarm set at {target_time}: {message}")
        return f"Alarm set at {target_time}: {message}"

    except Exception as e:
        log.error(f"[set_alarm] Exception: {e}", exc_info=True)
        return f"I'm sorry, an error occurred while setting the alarm."


@function_tool()
async def set_alarm(
        delay_seconds: int,
        message: str = "Time is up!"
) -> str:
    """
    Schedule a reminder or alarm after a relative delay in seconds.

    This function is intended for relative time alarms, e.g.,
    "Remind me in 10 minutes" or "Set an alarm in 1 hour".
    Internally, it converts the delay to an absolute datetime
    and calls `set_alarm_at`.

    Args:
        delay_seconds: Number of seconds from now until the alarm triggers.
        message: The reminder message to announce when the alarm fires.

    Returns:
        A confirmation message indicating the alarm has been set,
        or an error message if the delay is not positive.
    """

    try:
        if delay_seconds <= 0:
            return "Alarm time must be in the future."

        log.info(f"[set_alarm] Alarm set: {delay_seconds} {message}")

        now = TimeZone().now()
        target_dt = now + timedelta(seconds=delay_seconds)
        return await set_alarm_at(TimeZone().to_str(target_dt), message)

    except Exception as e:
        log.error(f"[set_alarm] Exception: {e}", exc_info=True)
        return f"I'm sorry, an error occurred while setting the alarm."
