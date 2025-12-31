# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：tst_action_control.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/28 19:55
"""
import json
from typing import Optional, List, Literal, Dict

from backend.common.log import log
from backend.common.wscore.coze.ctrl import Command, CommandType
from backend.common.device.repository import DeviceStateRepository

from backend.common.openai.llm.models import llm
from backend.common.openai.llm.intention.action.base import Action, timed_execute, ActionResult


class ActionControl(Action):
    """设备控制"""
    name = "control"

    def __init__(self):
        self._llm = llm

    @property
    def system_prompt(self) -> str:
        return """Structured Control Command Processor

        Role:
        - Convert natural language to standardized JSON commands with device_clients, action, value, raw_input.
        - Output pure JSON only, no explanatory text.

        Device Types:
        - light: Lighting device_clients
        - screen: Display device_clients
        - bluetooth: Bluetooth connection
        - volume: Volume control
        - playback: Media playback
        - mode: Device mode
        - microphone: Microphone device_clients

        Action Types:
        - on: Turn on
        - off: Turn off
        - adjust: Adjust parameter
        - pause: Pause playback
        - continue: Resume playback
        - next: Next track
        - prev: Previous track
        - jump: Jump to track
        - set: Set mode
        - mute: Enable mute
        - unmute: Disable mute
        - record: Start recording
        - stop_record: Stop recording

        Mode Types:
        - sleep: Sleep mode
        - child: Child mode
        - single_loop: Single track loop
        - list_loop: Playlist loop
        - shuffle: Shuffle mode
        - voice_command: Voice command mode
        - karaoke: Karaoke mode
        - meeting: Meeting mode

        Parameter Rules:
        - Volume: Integer 0-100 or ±n (e.g., 5, -10); vague adjustments (e.g., "a bit louder") map to 10, "a bit lower" to -10
        - Track: Positive integer (starting from 1)
        - Mode: Use mode type enum value
        - Others: null

        Error Handling:
        - Invalid input or conflicting commands: {"device_clients":"invalid","action":null,"value":"invalid input","raw_input":"..."}
        - Missing parameters: value set to null or default

        Examples:
        - "Turn on bedroom light" -> {"device_clients":"light","action":"on","value":null,"raw_input":"Turn on bedroom light"}
        - "Set volume to 50%" -> {"device_clients":"volume","action":"set","value":50,"raw_input":"Set volume to 50%"}
        - "Turn volume up a bit" -> {"device_clients":"volume","action":"adjust","value":10,"raw_input":"Turn volume up a bit"}
        - "Next song" -> {"device_clients":"playback","action":"next","value":null,"raw_input":"Next song"}
        - "Enable shuffle mode" -> {"device_clients":"mode","action":"set","value":"shuffle","raw_input":"Enable shuffle mode"}
        - "Invalid command" -> {"device_clients":"invalid","action":null,"value":"invalid input","raw_input":"Invalid command"}
        """

    @timed_execute(threshold_ms=1000)
    async def process(
            self, text: str, content: str,
            conversation_history: Optional[List[Dict[Literal["user", "assistant"], str]]] = None,
            device_repo: DeviceStateRepository = None,
            **kwargs
    ) -> ActionResult:
        llm_response = await self._call_llm(text, self._llm.LITE_MODEL_NAME)

        invalid_meta_data = Command.build_command(
            type=CommandType.CONTROL, cmd="invalid", params={}
        ).model_dump()

        try:
            resp = json.loads(llm_response)
            if isinstance(resp, dict):
                if resp.get("device_clients") == "invalid":
                    return ActionResult(
                        user_prompt=f"{resp.get('value') or 'Command not recognized. Please try again.'}",
                        meta_data=invalid_meta_data,
                    )
                resp = [resp]

            meta_data = Command.build_command(
                type=CommandType.CONTROL, cmd="list", params={"commands": resp}
            ).model_dump()
            return ActionResult(
                user_prompt=f"Command dispatched", meta_data=meta_data,
            )
        except Exception as ex:
            log.error(f"设备控制指令提取失败 - {ex}")
            return ActionResult(
                user_prompt=f"Command not recognized. Please try again.", meta_data=invalid_meta_data,
            )

    async def _call_llm(self, text: str, model_name: str, **kwargs) -> str:
        """统一的LLM调用"""
        text = f"""
            Current time: {self.en_formatted_date}
            User query: {text}
        """
        llm_response = await self._llm.query(
            text=text,
            system_prompt=self.system_prompt,
            model_name=model_name,
            **kwargs
        )

        log.debug(f"设备控制指令提取结果：：[text={text}, llm_response={llm_response}]")
        return llm_response
