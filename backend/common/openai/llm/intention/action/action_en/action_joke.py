# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：action_joke.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/28 19:55
"""
import random
from typing import Optional, List, Literal, Dict

from backend.common.device.repository import DeviceStateRepository

from backend.common.openai.llm.intention.action.base import Action, timed_execute, ActionResult


class ActionJoke(Action):
    """笑话"""
    name = "joke"

    joke_topics = [
        # Professions
        "programmer", "doctor", "lawyer", "teacher", "police officer", "chef", "farmer", "scientist", "artist",
        "driver", "construction worker", "firefighter", "soldier", "pilot", "astronaut", "journalist", "accountant",

        # Academic Subjects
        "math", "physics", "chemistry", "biology", "history", "geography", "philosophy", "psychology", "economics",

        # Daily Life
        "family", "school", "marriage", "parenting", "fitness", "weight loss", "shopping", "cooking", "pets",

        # Entertainment
        "movies", "music", "video games", "sports", "anime", "TV shows", "celebrity", "internet celebrity", "memes",

        # Technology
        "AI", "big data", "blockchain", "metaverse", "smartphones", "electric cars", "robots",

        # Humor Styles
        "puns", "dad jokes", "riddles", "anti-jokes", "dark humor", "satire", "adult humor",

        # Fantasy Themes
        "aliens", "superheroes", "vampires", "zombies", "wizards", "time travel", "parallel universe",

        # Holidays & Seasons
        "Chinese New Year", "Christmas", "Halloween", "Valentine's Day", "summer", "winter", "rainy days", "snow days",

        # Creative Categories
        "brain teasers", "absurd conversations", "witty comebacks", "funny ads", "dialect jokes", "international jokes"
    ]

    @property
    def system_prompt(self) -> str:
        return """Humorous Joke Generation Prompt Template

        Role:
        - You are a witty comedian, skilled at crafting short, joyful jokes.

        Requirements:
        - Content must be positive, avoiding offensive, sensitive, political, religious, or negative topics.
        - Generate a cohesive joke phrase using puns, twists, or daily life scenarios, 50-100 words, 3-5 sentences.
        - Use exaggeration or contrast to boost humor.
        - If a theme is specified, follow it; otherwise, prioritize daily life, then family themes.
        - If a style (e.g., pun) is specified, prioritize that style.

        Output Format:
        - Generate a complete joke phrase, without question-answer format.

        Example:
        The tomato blushes passing the salad dressing because it feels "ripe" too fast!
        """

    @timed_execute(threshold_ms=1000)
    async def process(
            self, text: str, content: str,
            conversation_history: Optional[List[Dict[Literal["user", "assistant"], str]]] = None,
            device_repo: DeviceStateRepository = None,
            **kwargs
    ) -> ActionResult:
        if content == "unknown":
            topic = random.choice(self.joke_topics)
            text = f"Please tell me a joke about '{topic}'"

        return ActionResult(
            user_prompt=f"""
                Current time: {self.en_formatted_date}
                Input: {text}
                Generate a relevant response considering:
                - Previous conversation history
                - Related data
            """
        )
