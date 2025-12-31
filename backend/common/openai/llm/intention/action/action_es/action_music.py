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

    NO_RESOURCE_TEMPLATE = "No se encontraron recursos coincidentes"
    PLAYING_TEMPLATE = "A continuación se reproduce"
    INVALID_TEMPLATE = "El servicio de música no está disponible temporalmente, por favor intente más tarde"
    AUTH_TEMPLATE = "Esta función requiere autorización de QQ Music, escanee el código QR"
