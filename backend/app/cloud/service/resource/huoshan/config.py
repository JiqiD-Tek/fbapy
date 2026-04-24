# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : config.py
@Author  : guhua@jiqid.com
@Date    : 2026/04/24 17:45
"""

from backend.core.conf import settings

PROJECT_MAP = {
    "default": {
        "appid": settings.BYTES_TTS_APPID.strip(),
        "token": settings.BYTES_TTS_TOKEN.strip(),
        "voice": {
            'S_GKcK2x2X1': '曲老师',
            'S_EKcK2x2X1': '虾球',
            'S_DKcK2x2X1': '米粒',
            'S_CKcK2x2X1': '旁白',
            'S_BKcK2x2X1': '珍棒',
            'S_AKcK2x2X1': '珍居',
            'S_zKcK2x2X1': '凯叔',
            'S_yKcK2x2X1': '成男温柔',
            'S_xKcK2x2X1': '成女温柔',
            'S_FKcK2x2X1': '成女活泼',
        }
    },
    "JS61": {
        "appid": settings.JS61_BYTES_TTS_APPID.strip(),
        "token": settings.JS61_BYTES_TTS_TOKEN.strip(),
        "voice": {
            'S_7V2ryDOZ1': '汤普森爸爸',
        }
    },
}
