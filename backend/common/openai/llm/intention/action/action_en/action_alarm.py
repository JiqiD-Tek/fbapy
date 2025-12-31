# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：tst_action_clock.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/28 19:55
"""

import re
from dataclasses import asdict
from datetime import datetime, time
from typing import Optional, List, Literal, Dict, Union

from backend.common.log import log
from backend.utils.timezone import timezone
from backend.common.device.model import Alarm, AlarmType
from backend.common.device.repository import DeviceStateRepository
from backend.common.wscore.coze.ctrl import Command, CommandType
from backend.common.openai.llm.models import llm
from backend.common.openai.llm.intention.action.base import Action, timed_execute, ActionResult


class ActionAlarm(Action):
    """闹钟工具"""
    name = "alarm"

    def __init__(self):
        self._llm = llm

    @property
    def system_prompt(self) -> str:
        return """Smart Alarm Clock Command Processor

        Role:
        - Convert natural language to standardized alarm commands (ADD/DEL/LIST).
        - Output structured commands only, no conversational responses.

        Commands:
        1. ADD (Create Alarm)
           - Syntax: ADD time=<YYYY-MM-DD HH:MM:SS or HH:MM:SS> [repeat=<schedule>] [label=<tag>]
           - Time: One-time (2025-08-12 09:00:00) or recurring (15:30:00).
           - Repeat: daily=0,1,2,3,4,5,6 | workdays=0,1,2,3,4 | weekend=5,6 | custom=0,2,4.
           - Example: "Daily wake-up at 7:30am" -> ADD time=07:30:00 repeat=0,1,2,3,4,5,6 label=Wakeup

        2. DEL (Delete Alarm)
           - Syntax: DEL [time=<time>] [label=<tag>] [repeat=<schedule>]
           - Supports combinations: time & label & repeat.
           - Example: "Cancel 9am meeting" -> DEL time=2025-08-12 09:00:00 label=Meeting

        3. LIST (Query Alarms)
           - Syntax: LIST [filter=<time|label|repeat>]
           - Shows all fields; supports filters.
           - Example: "Show all alarms" -> LIST

        Time Rules:
        - Relative: "In 2 hours" -> Current time + 2h (e.g., 2025-08-11 12:41:00).
        - Past: One-time tasks expire; recurring tasks defer to next cycle.
        - All-day: "Tomorrow" -> Tomorrow 00:00:00.

        Error Handling:
        - Invalid input: "ERROR: invalid input"
        - Missing parameters: Use defaults (time=unknown, label=unknown).
        - Conflicting parameters: Prioritize time > label > repeat.

        Examples:
        - "Meeting tomorrow at 9am" -> ADD time=2025-08-12 09:00:00 label=Meeting
        - "Gym Mon/Wed/Fri at 1pm" -> ADD time=13:00:00 repeat=0,2,4 label=Gym
        - "Remove daily alarms" -> DEL repeat=0,1,2,3,4,5,6
        - "Show meetings" -> LIST filter=label=Meeting
        """

    @timed_execute(threshold_ms=1000)
    async def process(
            self, text: str, content: str,
            conversation_history: Optional[List[Dict[Literal["user", "assistant"], str]]] = None,
            device_repo: DeviceStateRepository = None,
            **kwargs
    ) -> ActionResult:
        llm_response = await self._call_llm(text, self._llm.THINK_MODEL_NAME, conversation_history)
        return await self._handle_resp(device_repo, llm_response)

    async def _call_llm(
            self, text: str,
            model_name: str,
            conversation_history: Optional[List[Dict[Literal["user", "assistant"], str]]] = None,
            **kwargs) -> str:
        """统一的LLM调用"""
        text = f"""
            Current time: {self.en_formatted_date}
            User query: {text}
            Generate a relevant response considering:
                - Previous conversation history
        """

        llm_response = await self._llm.query(
            text=text,
            system_prompt=self.system_prompt,
            model_name=model_name,
            conversation_history=conversation_history,
            **kwargs,
        )

        log.debug(f"闹钟设置指令提取结果：[text={text}, llm_response={llm_response}]")
        return llm_response

    async def _handle_add_cmd(self, device_repo: DeviceStateRepository, alarm_resp: dict) -> ActionResult:
        """处理添加闹钟命令"""
        try:
            alarm = alarm_resp["data"]
            await device_repo.add_alarm(alarm)
            return self._create_success_result(
                cmd="ADD",
                message=f"Alarm added successfully. {self._trans_alarm(alarm)}",
                alarms=[alarm]
            )
        except KeyError:
            return self._create_error_result("ADD", "缺少闹钟数据")

    async def _handle_del_cmd(self, device_repo: DeviceStateRepository, cmd: str, alarms: list) -> ActionResult:
        """处理删除闹钟命令"""
        if not alarms:
            return self._create_success_result(cmd, "No matching alarms found.")

        alarms = await device_repo.del_alarm([alarm.id for alarm in alarms])
        deleted = [self._trans_alarm(item) for item in alarms]

        return self._create_success_result(
            cmd=cmd,
            message=f"The following alarms have been deleted:\n{'\n'.join(deleted)}",
            alarms=alarms
        )

    async def _handle_list_cmd(self, cmd: str, alarms: list) -> ActionResult:
        """处理列出闹钟命令"""
        if not alarms:
            return self._create_success_result(cmd, "No matching alarms found.")

        content = [self._trans_alarm(alarm) for alarm in alarms]
        return self._create_success_result(
            cmd=cmd,
            message=f"The following alarms have been find:\n{'\n'.join(content)}",
            alarms=alarms
        )

    def _create_success_result(self, cmd: str, message: str, alarms: List[Alarm] = None) -> ActionResult:
        """创建成功响应"""
        meta_data = Command.build_command(
            type=CommandType.ALARM, cmd=cmd.lower(),
            params={"alarms": [asdict(alarm) for alarm in alarms]} if alarms else {"alarms": []}
        ).model_dump()
        return ActionResult(
            user_prompt=message,
            meta_data=meta_data
        )

    def _create_error_result(self, cmd: str, message: str) -> ActionResult:
        """创建错误响应"""
        meta_data = Command.build_command(
            type=CommandType.ALARM, cmd="invalid",
            params={}
        ).model_dump()
        return ActionResult(
            user_prompt=f"操作失败: {message}",
            meta_data=meta_data
        )

    async def _handle_resp(self, device_repo: DeviceStateRepository, resp: str) -> ActionResult:
        """处理闹钟相关响应"""
        alarm_resp = self._handle_llm_resp(resp=resp)
        log.debug(f"处理指令结果：{alarm_resp}")

        cmd = alarm_resp.get("cmd", "")
        if cmd not in ("ADD", "DEL", "LIST"):
            return self._create_error_result(cmd, "无效指令")

        # 处理ADD命令
        if cmd == "ADD":
            return await self._handle_add_cmd(device_repo, alarm_resp)

        # 处理DEL和LIST命令
        alarms = await self._find_matching_alarms(device_repo, alarm_resp.get("conditions", {}))

        if cmd == "DEL":
            return await self._handle_del_cmd(device_repo, cmd, alarms)

        return await self._handle_list_cmd(cmd, alarms)

    async def _find_matching_alarms(self, device_repo: DeviceStateRepository, conditions: dict) -> List[Alarm]:
        """根据条件查找匹配的闹钟 """
        alarms = await device_repo.get_valid_alarms()

        # 1. 按标签过滤
        if label := conditions.get("label"):
            alarms = [alarm for alarm in alarms if alarm.label.lower() == label.lower()]

        # 2. 按时间过滤
        if trigger := conditions.get("time"):
            alarms = self._filter_by_trigger(alarms, trigger)

        # 3. 按重复周期过滤
        if repeat := conditions.get("repeat"):
            alarms = self._filter_by_repeat(alarms, repeat)

        return self._remove_duplicate_alarms(alarms)

    def _filter_by_trigger(self, alarms: List[Alarm], trigger: Union[datetime, time]) -> List[Alarm]:
        """根据触发时间过滤闹钟"""
        filtered = []
        for alarm in alarms:
            if alarm.alarm_type == AlarmType.PERIODIC:  # 周期性闹钟：精确匹配时间
                if alarm.trigger == trigger:
                    filtered.append(alarm)
                    continue
                if trigger.weekday() in alarm.repeat:
                    filtered.append(alarm)
                    continue
            else:  # 一次性闹钟：精确匹配时间
                if alarm.trigger == trigger:
                    filtered.append(alarm)
                    continue
                if trigger.hour == trigger.minute == trigger.second == 0 and alarm.trigger.date() == trigger.date():
                    filtered.append(alarm)
                    continue

        return filtered

    def _filter_by_repeat(self, alarms: List[Alarm], repeat: List[int]) -> List[Alarm]:
        """根据重复周期过滤闹钟"""
        filtered = []
        for alarm in alarms:
            if alarm.alarm_type == AlarmType.PERIODIC:
                # 周期性闹钟：检查是否包含所有指定的星期
                if all(day in alarm.repeat for day in repeat):
                    filtered.append(alarm)
            else:
                # 一次性闹钟：检查触发日是否在指定的星期中
                if alarm.trigger.weekday() in repeat:
                    filtered.append(alarm)

        return filtered

    def _remove_duplicate_alarms(self, alarms: List[Alarm]) -> List[Alarm]:
        """根据id去除重复闹钟"""
        seen_ids = set()
        unique_alarms = []

        for alarm in alarms:
            if alarm.id not in seen_ids:
                seen_ids.add(alarm.id)
                unique_alarms.append(alarm)

        return unique_alarms

    def _handle_llm_resp(self, resp: str) -> Dict:
        """处理标准化指令响应"""
        try:
            resp = resp.strip()
            if not resp:
                log.debug("大模型识别指令为空")
                return self._handle_invalid("Alarm Empty")

            if resp.startswith("ADD"):
                return self._handle_add(resp)
            if resp.startswith("DEL"):
                return self._handle_del(resp)
            if resp.startswith("LIST"):
                return self._handle_list(resp)

            log.error(f"闹钟参数异常: {resp}")
            return self._handle_invalid(f"Alarm Error: {resp}")
        except Exception as e:
            log.error(f"闹钟大模型输出处理失败：{e}")
            return {}

    def _handle_add(self, resp: str) -> Dict:
        """
        处理新增闹钟指令
        格式: ADD time=<时间> [repeat=<周期>] [label=<标签>]
        示例: ADD time=2023-09-01_09:00 repeat=1,3,5 label=会议
        """
        try:
            params = self._parse_params(resp[3:].strip())
            self._validate_params(params, ["time"])

            alarm = Alarm(
                trigger=self._parse_time(params["time"]),
                alarm_type=AlarmType.PERIODIC if "repeat" in params else AlarmType.NON_PERIODIC,
                repeat=self._parse_repeat(params.get("repeat", "")),
                label=params.get("label", "无"),
            )
            return {"cmd": "ADD", "data": alarm}
        except ValueError as e:
            log.debug(f"添加闹钟失败: {e}")
            return {}

    def _handle_del(self, resp: str) -> Dict:
        """
        处理删除闹钟指令
        格式: DEL id=<ID> | [time=<>] [label=<>] [repeat=<>]
        示例: DEL id=5 或 DEL label=会议 repeat=1,3,5
        """
        try:
            params = self._parse_params(resp[3:].strip())

            conditions = {}
            if "time" in params:
                conditions["time"] = self._parse_time(params["time"])
            if "label" in params:
                conditions["label"] = params["label"]
            if "repeat" in params:
                conditions["repeat"] = self._parse_repeat(params["repeat"])

            return {
                "cmd": "DEL",
                "conditions": conditions
            }
        except ValueError as e:
            log.debug(f"删除闹钟失败: {e}")
            return {}

    def _handle_list(self, resp: str) -> Dict:
        """
        处理查询指令
        格式: LIST [filter=<条件>]
        示例: LIST filter=time>2023-09-01
        """
        try:
            params = self._parse_params(resp[4:].strip())

            conditions = {}
            if "time" in params:
                conditions["time"] = self._parse_time(params["time"])
            if "label" in params:
                conditions["label"] = params["label"]
            if "repeat" in params:
                conditions["repeat"] = self._parse_repeat(params["repeat"])

            return {
                "cmd": "LIST",
                "conditions": conditions,
            }
        except ValueError as e:
            log.debug(f"查询闹钟失败: {e}")
            return {}

    @staticmethod
    def _handle_invalid(resp: str) -> Dict:
        """处理无效指令"""
        return {
            "error": "INVALID_COMMAND",
            "message": resp,
            "valid_commands": ["ADD", "DEL", "LIST"]
        }

    # ========== 工具函数 ==========
    @staticmethod
    def _parse_params(param_str: str) -> Dict[str, str]:
        """解析 key=value 参数，支持无引号的含空格时间"""
        params = {}
        # 正则调整：优先匹配完整时间格式（YYYY-MM-DD HH:MM:SS），再匹配普通值
        pattern = re.compile(
            r'(\w+)=('
            r'"[^"]*"|'  # 引号包裹的值
            r'\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}|'  # 时间格式（无引号）
            r'[^\s=]+'  # 普通值（无空格）
            r')(?=\s+\w+=|$)'
        )
        for match in pattern.finditer(param_str):
            key, value = match.groups()
            params[key] = value.strip('"')

        log.debug(f"Alarm params: {params}")
        return params

    @staticmethod
    def _validate_params(params: Dict, required: List[str]):
        """验证必要参数是否存在"""
        for field in required:
            if field not in params:
                raise ValueError(f"Missing required field: {field}")

    @staticmethod
    def _parse_time(time_str: str) -> Union[datetime, time]:
        for fmt in ["%Y-%m-%d %H:%M:%S", "%H:%M:%S", "%Y-%m-%d"]:
            try:
                dt = timezone.f_str(time_str, fmt)
                return dt.time() if fmt == "%H:%M:%S" else dt  # 返回 time 或 datetime
            except ValueError:
                continue
        raise ValueError(f"Invalid time format: {time_str}")

    @staticmethod
    def _parse_repeat(repeat_str: str) -> List[int]:
        """解析重复周期"""
        if not repeat_str:
            return []

        presets = {
            "workday": [0, 1, 2, 3, 4],
            "weekend": [5, 6],
            "daily": list(range(7))
        }
        if repeat_str in presets:
            return presets[repeat_str]

        try:
            return sorted({int(x) for x in repeat_str.split(",")})
        except ValueError:
            raise ValueError(f"Invalid repeat format: {repeat_str}")

    # ========== 格式转换函数 ==========

    @staticmethod
    def _trans_trigger(trigger):
        """转换触发器时间为可读字符串 """
        if isinstance(trigger, datetime):
            try:
                return timezone.t_str(trigger)  # 假设timezone.t_str是安全的格式化方法
            except (AttributeError, TypeError) as e:
                # 处理timezone.t_str可能出现的异常
                log.error(f"时间格式转换失败: {str(e)}")
                return str(trigger)  # 回退到基本的字符串表示

        return trigger

    def _trans_alarm(self, alarm):
        return (f"Time: {self._trans_trigger(alarm.trigger)}, "
                f"Recurrence: {self._trans_repeat(alarm.repeat)}, "
                f"Label: '{alarm.label}'")

    @staticmethod
    def _trans_repeat(repeat: list):
        """Convert repeat day numbers to human-readable text (English)"""
        # Predefined patterns
        patterns = {
            frozenset(range(7)): "Daily",
            frozenset(range(5)): "Weekdays",
            frozenset({5, 6}): "Weekends",
        }

        # Weekday mapping (ISO standard: Monday=0, Sunday=6)
        weekday_map = {
            0: "Monday",
            1: "Tuesday",
            2: "Wednesday",
            3: "Thursday",
            4: "Friday",
            5: "Saturday",
            6: "Sunday"
        }

        # Edge cases
        if not isinstance(repeat, list):
            return str(repeat)
        if not repeat:
            return "None"

        # Preprocess: deduplicate and sort
        unique_days = sorted(set(repeat))
        if len(unique_days) == 1:
            return weekday_map.get(unique_days[0], str(unique_days[0]))

        # Check predefined patterns
        if pattern_match := patterns.get(frozenset(unique_days)):
            return pattern_match

        # Consecutive day detection (supports cross-week)
        def is_consecutive(days: list) -> bool:
            _extended = days + [d + 7 for d in days]
            return any(
                all(_extended[i + j] == _extended[i] + j for j in range(len(days)))
                for i in range(len(days))
            )

        if is_consecutive(unique_days):
            # Find most compact continuous range
            extended = unique_days + [d + 7 for d in unique_days]
            for day in range(len(unique_days)):
                window = extended[day:day + len(unique_days)]
                if all(window[j] + 1 == window[j + 1] for j in range(len(window) - 1)):
                    start, end = window[0] % 7, window[-1] % 7
                    return f"{weekday_map[start]} to {weekday_map[end]}"

        # Default: return sorted weekday names
        return [weekday_map.get(d, str(d)) for d in sorted(unique_days)]
