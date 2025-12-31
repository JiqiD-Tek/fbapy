# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：action_music.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/28 19:55
"""
from dataclasses import asdict
from typing import Optional, List, Literal, Dict

from backend.common.log import log
from backend.common.wscore.coze.ctrl import Command, CommandType
from backend.common.device.repository import DeviceStateRepository
from backend.common.openapi.music.qq_music import qq_music, AuthorizedError
from backend.common.openapi.music.open_music import open_music

from backend.common.openai.llm.intention.action.base import Action, timed_execute, ActionResult


class ActionMusic(Action):
    """音乐播放与推荐工具"""
    name = "music"

    def __init__(self):
        self.api = qq_music

    @property
    def system_prompt(self) -> str:
        """音乐服务结构化指令"""
        return """

        """

    NO_RESOURCE_TEMPLATE = "No matching resources found."
    PLAYING_TEMPLATE = "Now playing"
    INVALID_TEMPLATE = "Music service is temporarily unavailable. Please try again later."
    AUTH_TEMPLATE = "This feature requires QQ Music authorization. Please scan the QR code to log in."

    @timed_execute(threshold_ms=1000)
    async def process(
            self, text: str, content: str,
            conversation_history: Optional[List[Dict[Literal["user", "assistant"], str]]] = None,
            device_repo: DeviceStateRepository = None,
            **kwargs
    ) -> ActionResult:
        """ content=周杰伦的歌 """
        log.debug(f"识别播放内容: {content}")
        song, singer = content.split("|")

        if song != "unknown":
            return await self.query_songs(song, device_repo)
        if singer != "unknown":
            return await self.query_songs(singer, device_repo)

        return await self.query_songs("popular music", device_repo)

    async def query_songs(self, content, device_repo: DeviceStateRepository):
        """ 查询歌曲列表 """
        # 常量定义
        invalid_meta_data = Command.build_command(
            type=CommandType.MUSIC,
            cmd="invalid",
            params={}
        ).model_dump()

        ip = "221.226.35.218"  # 固定方便测试 device_repo.get_field("ip")
        try:
            songs = await self.api.get_songs(
                query=content, device_id=device_repo.device_id, client_ip=ip)

            if not songs:
                return ActionResult(
                    user_prompt=self.NO_RESOURCE_TEMPLATE,
                    meta_data=invalid_meta_data
                )

            meta_data = Command.build_command(
                type=CommandType.MUSIC,
                cmd="play",
                params={"songs": [asdict(song) for song in songs]}
            ).model_dump()
            return ActionResult(
                user_prompt=f"{self.PLAYING_TEMPLATE}：{songs[0].song_name}",
                meta_data=meta_data,
            )

        except AuthorizedError:
            return await self._handle_auth_error(device_repo.device_id, client_ip=ip)
        except Exception as e:
            log.error(f"歌曲查询失败 [device:{device_repo.device_id} - {e}]", exc_info=True)
            songs = open_music.get_songs(query="music")
            meta_data = Command.build_command(
                type=CommandType.MUSIC,
                cmd="play",
                params={"songs": [asdict(song) for song in songs]}
            ).model_dump()
            return ActionResult(
                user_prompt=f"{self.PLAYING_TEMPLATE}：{songs[0].song_name}",
                meta_data=meta_data
            )

    async def _handle_auth_error(self, device_id: str, client_ip: str) -> ActionResult:
        code_resp = await self.api.login_by_qr_code(device_id=device_id, client_ip=client_ip)
        meta_data = Command.build_command(
            type=CommandType.MUSIC,
            cmd="auth",
            params={"code": code_resp["sdk_qr_code"]}
        ).model_dump()
        return ActionResult(
            meta_data=meta_data,
            user_prompt=self.AUTH_TEMPLATE,
        )
