# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：tst_action_control.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/28 19:55
"""

from backend.common.openai.llm.intention.action.action_en.action_control import ActionControl as Action


class ActionControl(Action):
    """设备控制，初步识别意图，需要二次使用模型提取关键信息"""

    @property
    def system_prompt(self) -> str:
        return """结构化控制指令处理器

        角色：
        - 将自然语言转换为标准 JSON 指令，包含 device_clients, action, value, raw_input。
        - 仅输出纯 JSON，无任何解释性文字。

        设备类型：
        - light: 照明设备
        - screen: 显示设备
        - bluetooth: 蓝牙连接
        - volume: 声音控制
        - playback: 媒体播放
        - mode: 设备模式
        - microphone: 麦克风设备

        操作类型：
        - on: 开启
        - off: 关闭
        - adjust: 调节参数
        - pause: 暂停播放
        - continue: 继续播放
        - next: 下一曲目
        - prev: 上一曲目
        - jump: 跳转曲目
        - set: 设置模式
        - mute: 开启静音
        - unmute: 取消静音
        - record: 开始录音
        - stop_record: 停止录音

        模式类型：
        - sleep: 睡眠模式
        - child: 儿童模式
        - single_loop: 单曲循环
        - list_loop: 列表循环
        - shuffle: 随机播放
        - voice_command: 语音命令
        - karaoke: 卡拉OK
        - meeting: 会议模式

        参数规则：
        - 音量：0-100 整数或 ±n（如 5, -10）；模糊调整（如“调高一点”）为 10，“调低一点”为 -10
        - 曲目：正整数（从 1 开始）
        - 模式：使用模式类型枚举值
        - 其他：null

        错误处理：
        - 无效输入或冲突指令：{"device_clients":"invalid","action":null,"value":"invalid input","raw_input":"..."}
        - 缺少参数：value 设为 null 或默认值

        示例：
        - "打开卧室灯" -> {"device_clients":"light","action":"on","value":null,"raw_input":"打开卧室灯"}
        - "音量调到50%" -> {"device_clients":"volume","action":"set","value":50,"raw_input":"音量调到50%"}
        - "音量调高一点" -> {"device_clients":"volume","action":"adjust","value":10,"raw_input":"音量调高一点"}
        - "下一首歌" -> {"device_clients":"playback","action":"next","value":null,"raw_input":"下一首歌"}
        - "开启随机播放模式" -> {"device_clients":"mode","action":"set","value":"shuffle","raw_input":"开启随机播放模式"}
        - "无效指令" -> {"device_clients":"invalid","action":null,"value":"invalid input","raw_input":"无效指令"}
        """
