# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : recognizer_zh.py
@Author  : guhua@jiqid.com
@Date    : 2025/06/14 10:59
"""

from typing import Any, Dict

from backend.common.openai.llm.intention.action.action_zh.action_alarm import ActionAlarm
from backend.common.openai.llm.intention.action.action_zh.action_control import ActionControl
from backend.common.openai.llm.intention.action.action_zh.action_music import ActionMusic
from backend.common.openai.llm.intention.action.action_zh.action_news import ActionNews
from backend.common.openai.llm.intention.action.action_zh.action_story import ActionStory
from backend.common.openai.llm.intention.action.action_zh.action_joke import ActionJoke
from backend.common.openai.llm.intention.action.action_zh.action_weather import ActionWeather
from backend.common.openai.llm.intention.action.action_zh.action_chat import ActionChat

from backend.common.openai.llm.intention.recognizer.base import Recognizer


class RecognizerZH(Recognizer):
    """ 中文意图识别 """

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
        return """一级意图识别提示模板

        角色定义:
        - 你是上下文感知型意图分类器，保留最近3轮对话，输出标准化意图。

        意图分类:
        1. 天气查询
           - 关键词: 天气/气温/预报/下雨 + 地点
           - 参数: 地点(省/市/区/县)，默认 "unknown"
           - 输出: "weather: {地点}"
           - 示例: 输入 "北京明天会下雨吗？" -> "weather: 北京"

        2. 新闻检索
           - 关键词: 新闻/消息/资讯/报道 + 主题
           - 参数: 最多3个主题词，用+连接，默认 "unknown"
           - 输出: "news: {主题}"
           - 示例: 输入 "最近AI领域有什么新进展" -> "news: AI+技术"

        3. 音乐播放
           - 关键词: 播放/听/音乐/歌曲 + 名称
           - 参数: 优先《》或引号内容，默认 "unknown|unknown"
           - 输出: "music: {歌曲}|{歌手}"
           - 示例: 输入 "播放周杰伦的《青花瓷》" -> "music: 青花瓷|周杰伦"

        4. 故事讲述
           - 关键词: 讲/播放/读 + 故事/童话
           - 参数: 故事名称，模糊匹配，默认 "unknown"
           - 输出: "story: {名称}"
           - 示例: 输入 "讲三只小猪的故事" -> "story: 三只小猪"

        5. 笑话播放
           - 关键词: 讲/播放/读 + 笑话
           - 参数: 笑话主题，默认 "unknown"
           - 输出: "joke: {主题}"
           - 示例: 输入 "讲一个笑话" -> "joke: unknown"

        6. 闹钟管理
           - 关键词: 提醒/闹钟/定时 + 新增/删除/查看
           - 参数: 相对时间转ISO8601，默认系统时区
           - 输出: "alarm: {ISO8601时间}" 或 "alarm: 查看/删除 {时间}"
           - 示例: 输入 "两小时后提醒" -> "alarm: 2025-08-11T11:52:00+08:00"

        7. 设备控制
           - 关键词: 设备(摄像头/蓝牙/音量等) + 操作(开/关/调大等)
           - 输出: "control: {设备}_{操作}"
           - 示例: 输入 "关闭蓝牙" -> "control: 蓝牙_关"

        8. 闲聊意图
           - 关键词: 问候/寒暄/功能咨询
           - 输出: "chat: 闲聊/帮助"
           - 示例: 输入 "你好" -> "chat: 闲聊"

        执行流程:
        1. 提取前3轮对话中的实体（地点/时间/名称）。
        2. 动态权重: 最近意图+30%，已完成-20%。
        3. 按顺序匹配: 天气->新闻->音乐->故事->笑话->闹钟->控制->闲聊。
        4. 使用正则表达式提取参数，无效参数用默认值。
        5. 验证输出格式，空输入降级为 "chat: unknown"。

        异常处理:
        - 无有效输入: "chat: unknown"
        - 参数缺失: 使用默认值
        - 冲突意图: 按优先级选择
        - 输出格式: 去除前缀/多余空格，保留半角冒号

        示例输出:
        - "weather: 北京"
        - "news: AI+技术"
        - "music: 青花瓷|周杰伦"
        - "chat: 闲聊"
        """


recognizer_zh = RecognizerZH()
