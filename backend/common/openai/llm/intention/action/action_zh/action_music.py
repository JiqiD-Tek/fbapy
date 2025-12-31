# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：action_music.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/28 19:55
"""

from backend.common.openai.llm.intention.action.action_en.action_music import ActionMusic as Action


class ActionMusic(Action):
    """音乐播放与推荐工具"""

    @property
    def system_prompt(self) -> str:
        """音乐服务结构化指令"""
        return """

        """

    NO_RESOURCE_TEMPLATE = "没有找到匹配的资源"  # No matching resources found.
    PLAYING_TEMPLATE = "下面为您播放"  # Now playing
    INVALID_TEMPLATE = "音乐服务暂时不可用，请稍后重试"  # Music service is temporarily unavailable...
    AUTH_TEMPLATE = "该功能需要授权QQ音乐，请扫描二维码"  # This feature requires QQ Music authorization...
