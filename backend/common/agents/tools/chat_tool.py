# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : tst_action_default.py
@Author  : guhua@jiqid.com
@Date    : 2025/05/28 19:55
"""
from typing import Optional, List, Literal, Dict

from backend.common.agents.prompt import build_user_prompt
from backend.common.agents.tools.base import Tool, timed_execute, ToolResult


class ChatTool(Tool):
    name = "chat"  # 闲聊

    @timed_execute(threshold_ms=1000)
    async def process(
            self, text: str, content: str,
            conversation_history: Optional[List[Dict[Literal["user", "assistant"], str]]] = None,
            chat_config: dict = None,
            **kwargs
    ) -> ToolResult:
        """ content=南京 """
        user_prompt = build_user_prompt(text, chat_config)
        return ToolResult(user_prompt=user_prompt)
