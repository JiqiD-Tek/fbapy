# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : tools.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/20 09:44
"""

import asyncio

from datetime import timedelta

from langchain_community.tools import DuckDuckGoSearchRun

from backend.app.live.agents.api_clients.weather_api import open_weather_map
from backend.app.live.agents.core.llm.tool_context import function_tool
from backend.common.log import log
from backend.utils.timezone import TimeZone

duck_tool = DuckDuckGoSearchRun()


@function_tool()
async def get_weather(city: str):
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

    log.info(f'[get_weather] Retrieving weather for English city name: {city}')
    try:
        return await open_weather_map.get_weather_info(city)
    except Exception as e:
        log.error(f'[get_weather] Exception for {city}: {e}')
        return f"I'm sorry, an error occurred while retrieving the weather for {city}."


@function_tool()
async def web_search(query: str, num_results: int = 3) -> str:
    """
    Perform a web search using DuckDuckGo and return the top results.

    Args:
        query: The search query string.
        num_results: Number of top results to return (default 3).

    Returns:
        A formatted string of search results, numbered.
    """

    log.info(f'[web_search] Searching the web for: {query}')
    try:
        resp = await asyncio.to_thread(duck_tool.run, query)

        lines = [line.strip() for line in resp.split('\n') if line.strip()]
        top_results = lines[:num_results]

        if not top_results:
            return f"No results found for '{query}'."

        formatted_results = '\n'.join(f'{i + 1}. {r}' for i, r in enumerate(top_results))
        log.info(f"[web_search] Top {len(top_results)} results for '{query}':\n{formatted_results}")

        return formatted_results

    except Exception as e:
        log.error(f"[web_search] Error during search for '{query}': {e}", exc_info=True)
        return f"I'm sorry, an error occurred while searching for '{query}'."


@function_tool()
async def exit_session() -> str:
    """
    Trigger an exit or stop of the assistant session.

    This function is intended to be called when the user wants to
    end the session or stop the assistant (e.g., "exit", "stop", "bye").

    Returns:
        A semantic confirmation that the exit was requested.
        The actual session termination should be handled by the runtime or agent.
    """

    log.info('[exit_session] Exit requested by user')

    try:
        return 'Exit requested.'

    except Exception as e:
        log.error(f'[exit_session] Error during exit: {e}', exc_info=True)
        return "I'm sorry, an error occurred while exiting"


@function_tool()
async def set_alarm_at(target_time: str, message: str = 'Time to wake up!') -> str:
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
            return 'The alarm time must be in the future.'

        log.info(f'[set_alarm] Alarm set at {target_time}: {message}')
        return f'Alarm set at {target_time}: {message}'

    except Exception as e:
        log.error(f'[set_alarm] Exception: {e}', exc_info=True)
        return "I'm sorry, an error occurred while setting the alarm."


@function_tool()
async def set_alarm(delay_seconds: int, message: str = 'Time is up!') -> str:
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
            return 'Alarm time must be in the future.'

        log.info(f'[set_alarm] Alarm set: {delay_seconds} {message}')

        now = TimeZone().now()
        target_dt = now + timedelta(seconds=delay_seconds)
        return await set_alarm_at(TimeZone().to_str(target_dt), message)

    except Exception as e:
        log.error(f'[set_alarm] Exception: {e}', exc_info=True)
        return "I'm sorry, an error occurred while setting the alarm."
