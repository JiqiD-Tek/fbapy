# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : recognizer_en.py
@Author  : guhua@jiqid.com
@Date    : 2025/06/14 10:59
"""

from typing import Any, Dict

from backend.common.openai.llm.intention.action.action_en.action_alarm import ActionAlarm
from backend.common.openai.llm.intention.action.action_en.action_control import ActionControl
from backend.common.openai.llm.intention.action.action_en.action_music import ActionMusic
from backend.common.openai.llm.intention.action.action_en.action_news import ActionNews
from backend.common.openai.llm.intention.action.action_en.action_story import ActionStory
from backend.common.openai.llm.intention.action.action_en.action_joke import ActionJoke
from backend.common.openai.llm.intention.action.action_en.action_weather import ActionWeather
from backend.common.openai.llm.intention.action.action_en.action_chat import ActionChat

from backend.common.openai.llm.intention.recognizer.base import Recognizer


class RecognizerEN(Recognizer):
    """ 英文意图识别 """

    @staticmethod
    def _init_action_registry() -> Dict[str, Any]:
        return {
            cls.name: cls() for cls in [
                ActionWeather, ActionNews, ActionMusic,
                ActionStory, ActionJoke, ActionAlarm, ActionControl,
            ]
        }

    def _get_default_action(self):
        """默认动作工厂方法"""
        return ActionChat()

    @property
    def system_prompt(self) -> str:
        return """Primary Intent Recognition Prompt Template

        Role:
        - You are a context-aware intent classifier, retaining the last 3 conversation turns, outputting standardized intents.

        Intent Classification:
        1. Weather Query
           - Keywords: weather/temperature/forecast/rain + location
           - Parameters: location (city/county) in English, default "unknown"
           - Output: "weather: {location}"
           - Example: Input "Will it rain in New York tomorrow?" -> "weather: New York"

        2. News Retrieval
           - Keywords: news/update/report + topic
           - Parameters: up to 3 topic words, joined by +, default "unknown"
           - Output: "news: {topic}"
           - Example: Input "What's new in AI?" -> "news: AI+technology"

        3. Music Playback
           - Keywords: play/listen/music/song + name
           - Parameters: prioritize 《》 or quotes, default "unknown|unknown"
           - Output: "music: {song}|{artist}"
           - Example: Input "Play 《Bohemian Rhapsody》 by Queen" -> "music: Bohemian Rhapsody|Queen"

        4. Story Telling
           - Keywords: tell/play/read + story/fairytale
           - Parameters: story name, fuzzy matching, default "unknown"
           - Output: "story: {name}"
           - Example: Input "Tell the story of Little Red Riding Hood" -> "story: Little Red Riding Hood"

        5. Joke Playback
           - Keywords: tell/play/read + joke
           - Parameters: joke theme, default "unknown"
           - Output: "joke: {theme}"
           - Example: Input "Tell a joke" -> "joke: unknown"

        6. Alarm Management
           - Keywords: remind/alarm/set + add/delete/view
           - Parameters: relative time to ISO8601, default system timezone
           - Output: "alarm: {ISO8601 time}" or "alarm: view/delete {time}"
           - Example: Input "Remind me in two hours" -> "alarm: 2025-08-11T11:52:00+08:00"

        7. Device Control
           - Keywords: device_clients (camera/bluetooth/volume) + action (on/off/increase)
           - Output: "control: {device_clients}_{action}"
           - Example: Input "Turn off bluetooth" -> "control: bluetooth_off"

        8. Chat Intents
           - Keywords: greetings/general questions/help
           - Output: "chat: chat/help"
           - Example: Input "Hello" -> "chat: chat"

        Execution Flow:
        1. Extract entities (location/time/name) from last 3 conversation turns.
        2. Adjust weights: recent intent +30%, completed intent -20%.
        3. Match in order: weather->news->music->story->joke->alarm->control->chat.
        4. Use regex for parameter extraction, default values for invalid parameters.
        5. Validate output format, empty input degrades to "chat: unknown".

        Error Handling:
        - Invalid input: "chat: unknown"
        - Missing parameters: use defaults
        - Conflicting intents: prioritize by order
        - Output format: remove extra spaces, use half-width colon

        Example Outputs:
        - "weather: New York"
        - "news: AI+technology"
        - "music: Bohemian Rhapsody|Queen"
        - "chat: chat"
        """


recognizer_en = RecognizerEN()
