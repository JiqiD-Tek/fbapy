# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：tst_action_clock.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/28 19:55
"""

from typing import List
from dataclasses import asdict

from backend.common.device.model import Alarm
from backend.common.device.repository import DeviceStateRepository
from backend.common.wscore.coze.ctrl import Command, CommandType

from backend.common.openai.llm.intention.action.base import ActionResult
from backend.common.openai.llm.intention.action.action_en.action_alarm import ActionAlarm as Action


class ActionAlarm(Action):
    """闹钟工具，初步识别意图，需要二次使用模型提取关键信息"""

    @property
    def system_prompt(self) -> str:
        return """智能闹钟指令处理器

        角色：
        - 将自然语言转换为标准化的闹钟指令（ADD/DEL/LIST）。
        - 仅输出结构化指令，支持多轮对话上下文。

        指令：
        1. ADD（新增闹钟）
           - 语法：ADD time=<YYYY-MM-DD HH:MM:SS或HH:MM:SS> [repeat=<周期>] [label=<标签>]
           - 时间：非周期（2025-08-12 09:00:00）或周期（15:30:00）。
           - 周期：每天=0,1,2,3,4,5,6 | 工作日=0,1,2,3,4 | 周末=5,6 | 自定义=0,2,4。
           - 示例：“每天7:30起床” -> ADD time=07:30:00 repeat=0,1,2,3,4,5,6 label=起床

        2. DEL（删除闹钟）
           - 语法：DEL [time=<时间>] [label=<标签>] [repeat=<周期>]
           - 支持组合：时间 & 标签 & 周期。
           - 示例：“取消明天9点会议” -> DEL time=2025-08-12 09:00:00 label=会议

        3. LIST（查询闹钟）
           - 语法：LIST [filter=<时间|标签|周期>]
           - 显示所有字段；支持过滤。
           - 示例：“查看所有闹钟” -> LIST

        时间规则：
        - 相对时间：“两小时后” -> 当前时间 + 2小时（如 2025-08-11 12:41:00）。
        - 过去时间：非周期任务过期；周期任务顺延至下一周期。
        - 全天事件：“明天” -> 明天00:00:00。

        错误处理：
        - 无效输入：“ERROR: invalid input”
        - 缺少参数：使用默认值（time=unknown，label=unknown）。
        - 冲突参数：优先级为时间 > 标签 > 周期。

        示例：
        - “明天9点开会” -> ADD time=2025-08-12 09:00:00 label=会议
        - “每周一三五13点健身” -> ADD time=13:00:00 repeat=0,2,4 label=健身
        - “取消每天的闹钟” -> DEL repeat=0,1,2,3,4,5,6
        - “显示明天会议” -> LIST filter=time=2025-08-12 09:00:00&label=会议
        """

    async def _handle_add_cmd(self, device_repo: DeviceStateRepository, alarm_resp: dict) -> ActionResult:
        """处理添加闹钟命令"""
        try:
            alarm = alarm_resp["data"]
            await device_repo.add_alarm(alarm)
            return self._create_success_result(
                cmd="ADD",
                message=f"添加闹钟成功，{self._trans_alarm(alarm)}",
                alarms=[alarm]
            )
        except KeyError:
            return self._create_error_result("ADD", "缺少闹钟数据")

    async def _handle_del_cmd(self, device_repo: DeviceStateRepository, cmd: str, alarms: list) -> ActionResult:
        """处理删除闹钟命令"""
        if not alarms:
            return self._create_success_result(cmd, "未找到匹配的闹钟")

        alarms = await device_repo.del_alarm([alarm.id for alarm in alarms])
        deleted = [self._trans_alarm(item) for item in alarms]

        return self._create_success_result(
            cmd=cmd,
            message=f"已删除以下闹钟:\n{'\n'.join(deleted)}",
            alarms=alarms
        )

    async def _handle_list_cmd(self, cmd: str, alarms: list) -> ActionResult:
        """处理列出闹钟命令"""
        if not alarms:
            return self._create_success_result(cmd, "未找到匹配的闹钟")

        content = [self._trans_alarm(alarm) for alarm in alarms]
        return self._create_success_result(
            cmd=cmd,
            message=f"找到以下闹钟:\n{'\n'.join(content)}",
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

    def _trans_alarm(self, alarm):
        return (f"时间为: {self._trans_trigger(alarm.trigger)}, "
                f"重复周期为: {self._trans_repeat(alarm.repeat)}， "
                f"标签为: {alarm.label}")

    @staticmethod
    def _trans_repeat(repeat: list):
        """转换重复日期的数字表示为可读文本"""
        # 定义常用组合
        patterns = {
            frozenset(range(7)): "每天",
            frozenset(range(5)): "工作日",
            frozenset({5, 6}): "周末",
        }

        # 星期映射（ISO标准：周一=0，周日=6）
        weekday_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日", }

        # 边界条件处理
        if not isinstance(repeat, list):
            return str(repeat)
        if not repeat:
            return "无"

        # 预处理：去重排序
        unique_days = sorted(set(repeat))
        if len(unique_days) == 1:
            return weekday_map.get(unique_days[0], str(unique_days[0]))

        # 检查预定义模式
        if pattern_match := patterns.get(frozenset(unique_days)):
            return pattern_match

        # 连续日期检测（支持跨周）
        def is_consecutive(days: list) -> bool:
            _extended = days + [d + 7 for d in days]
            return any(
                all(_extended[i + j] == _extended[i] + j for j in range(len(days)))
                for i in range(len(days))
            )

        if is_consecutive(unique_days):
            # 找到最紧凑的连续区间
            extended = unique_days + [d + 7 for d in unique_days]
            for day in range(len(unique_days)):
                window = extended[day:day + len(unique_days)]
                if all(window[j] + 1 == window[j + 1] for j in range(len(window) - 1)):
                    start, end = window[0] % 7, window[-1] % 7
                    return f"{weekday_map[start]}到{weekday_map[end]}"

        # 默认返回排序后的星期名称
        return [weekday_map.get(d, str(d)) for d in sorted(unique_days)]
