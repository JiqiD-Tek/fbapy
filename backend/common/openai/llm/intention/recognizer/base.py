# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : recognizer_zh.py
@Author  : guhua@jiqid.com
@Date    : 2025/06/19 14:04
"""

import re
import traceback
from abc import ABC, abstractmethod

from typing import Optional, Dict, Tuple, Any, Literal, List
from dataclasses import dataclass, field

from backend.common.log import log
from backend.common.openai.llm.models import llm
from backend.common.device.repository import DeviceStateRepository


@dataclass(frozen=True)
class Intention:
    """标准化意图表示（中英文通用）。

    属性:
        intent: 识别的意图名称。
        content: 意图内容。
        user_prompt: 用户提示词（可选）。
        system_prompt: 系统提示词（可选）。
        meta_data: 附加元数据（默认空字典）。
    """
    intent: str
    content: str
    user_prompt: Optional[str] = None
    system_prompt: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)


class Recognizer(ABC):
    """意图识别基类"""

    # 预编译正则表达式，支持引号和灵活的空格、分隔符
    _INTENT_PATTERN = re.compile(r'^\s*(?:"|\')?([^:：|]+?)(?:"|\')?\s*[:：|]\s*(?:"|\')?(.*?)(?:"|\')?\s*$')

    def __init__(self):
        self._action_registry = self._init_action_registry()
        self._llm = llm

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """获取系统提示词，子类必须实现。  """
        pass

    @staticmethod
    @abstractmethod
    def _init_action_registry() -> Dict[str, Any]:
        """初始化动作注册表，子类必须实现。  """
        pass

    @abstractmethod
    def _get_default_action(self):
        """默认动作工厂方法。 """
        pass

    async def detect(
            self, text: str,
            model_name: str = llm.LITE_MODEL_NAME,
            conversation_history: Optional[List[Dict[Literal["user", "assistant"], str]]] = None,
            device_repo: DeviceStateRepository = None,
            **kwargs) -> Intention:
        """
        执行意图识别查询
        Args:
            text: 用户输入文本
            model_name: 使用的大模型名称 默认使用最小模型（速度快）
            conversation_history: 对话历史
            device_repo: 设备存储
            **kwargs: 传递给意图识别的额外参数

        Returns:
            Intention 对象包含识别结果
        """
        try:
            llm_response = await self._call_llm(text, model_name, conversation_history)
            intent, content = self.extract_intent_content(llm_response)
            log.debug(
                f"意图处理器解析完成: text={text}, response={llm_response}, intent={intent}, content={content}")

            action = self._action_registry.get(intent, self._get_default_action())
            try:
                action_result = await action.process(
                    text=text,
                    content=content,
                    conversation_history=conversation_history,
                    device_repo=device_repo,
                    **kwargs
                )
                return Intention(
                    intent=intent,
                    content=content,
                    user_prompt=action_result.user_prompt,
                    system_prompt=getattr(action, 'system_prompt', None),
                    meta_data=action_result.meta_data,
                )
            except Exception as ex:
                f"动作处理失败 [Intent:{intent} - {ex} - {traceback.format_exc()}]"
                return Intention(
                    intent=intent,
                    content=content,
                    user_prompt=text,
                    system_prompt=None
                )
        except Exception as ex:
            log.error(f"意图识别失败 [Text:{text} - {ex} - {traceback.format_exc()}]")
            raise RuntimeError(f"意图识别失败: {ex}") from ex

    async def _call_llm(
            self, text: str,
            model_name: str,
            conversation_history: Optional[List[Dict[Literal["user", "assistant"], str]]] = None,
    ) -> str:
        """统一的LLM调用"""
        try:
            return await self._llm.query(
                text=text,
                system_prompt=self.system_prompt,
                model_name=model_name,
                conversation_history=conversation_history,
            )
        except Exception as ex:
            log.error(f"LLM调用失败 [Model:{model_name} - Text:{text} - {ex} - {traceback.format_exc()}]")
            raise

    @classmethod
    def extract_intent_content(cls, response: str) -> Tuple[Optional[str], str]:
        """从大模型响应中提取意图和内容。 """
        if not response or not isinstance(response, str):
            return None, ""

        response = response.strip()
        if match := cls._INTENT_PATTERN.match(response):
            intent, content = match.group(1).strip(), match.group(2).strip()
            return intent, content

        return None, response
