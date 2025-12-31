# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : tst_action_weather.py
@Author  : guhua@jiqid.com
@Date    : 2025/05/28 19:55
"""

from backend.common.openapi.amap.amap_client import amap_client
from backend.common.openai.llm.intention.action.action_en.action_weather import ActionWeather as Action


class ActionWeather(Action):
    """天气查询工具（支持实时数据口语化播报）"""

    def __init__(self):
        self.api = amap_client
        self.amap = amap_client

    @property
    def system_prompt(self) -> str:
        return """天气播报提示模板

        数据规范:
        - 使用API原始数据，禁止推测或补充未提供数据。
        - 缺失数据标注为“暂无”。
        - 单位: 温度用摄氏度（“低到高”，如“10到25度”），风力用等级（“3到4级”），风向用东南西北（如“东北风”）。

        播报模板:
        {地点}{日期}天气播报：
        - 温度: {温度}
        - 天气: {天气现象}
        - 风力: {风力}级{风向}
        提示: {生活建议}

        异常处理:
        - 数据缺失: “无法获取{地点}的{缺失数据}，请稍后重试。”
        - 极端天气: “预警：{预警内容}，建议：{防护措施}。”

        禁止事项:
        - 使用API原始术语（如“moderate rain”）。
        - 提及具体时间点（如“14:30”）。
        - 包含未验证的建议或计算公式。
        """
