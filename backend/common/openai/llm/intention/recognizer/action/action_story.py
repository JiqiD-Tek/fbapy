# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：action_story.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/28 19:55
"""
from backend.common.openai.llm.intention.recognizer.action.action_chat import ActionChat


class ActionStory(ActionChat):
    """故事播放"""
    name = "story"
