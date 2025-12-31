import os
import time
import json
import queue
import pyaudio
import asyncio
import logging
import threading

import tkinter as tk
from datetime import datetime
from tkinter import scrolledtext, ttk
from typing import Optional

from cozepy import (
    COZE_CN_BASE_URL,
    AsyncCoze,
    AsyncWebsocketsChatClient,
    AsyncWebsocketsChatEventHandler,
    ChatUpdateEvent,
    ConversationAudioDeltaEvent,
    ConversationChatCompletedEvent,
    ConversationChatCanceledEvent,
    ConversationAudioTranscriptCompletedEvent,
    ConversationMessageCompletedEvent,
    InputAudio,
    InputAudioBufferAppendEvent,
    TokenAuth,
    setup_logging,
)
from cozepy.log import log_info
from cozepy.websockets.chat import (
    ConversationAudioTranscriptUpdateEvent,
    ConversationMessageDeltaEvent,
    ConversationAudioCompletedEvent
)

from dotenv import load_dotenv

load_dotenv()  # 加载 .env 文件

# 音频参数设置
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
INPUT_BLOCK_TIME = 0.03  # 30ms per block

setup_logging(logging.getLevelNamesMapping().get(os.getenv("COZE_LOG").upper(), logging.INFO))


class ChatEventHandler(AsyncWebsocketsChatEventHandler):
    def __init__(self, gui):
        self.gui = gui
        self.first_audio = True

    async def on_conversation_audio_delta(
            self, cli: AsyncWebsocketsChatClient, event: ConversationAudioDeltaEvent
    ):
        try:
            audio_data = event.data.get_audio()
            if not audio_data:  # 播放完毕
                return

            if self.first_audio:
                self.first_audio = False
                self.gui.status_label.config(text="正在播放回复...")
                self.gui.update_chat_display("正在回复...", is_user=False)
                # self.gui.root.after(5000, self.gui.resume_recording)  # 延迟5秒重新录音

            self.gui.is_playing = True
            self.gui.playback_queue.put(audio_data)  # 将音频数据放入播放队列
        except Exception as e:
            log_info(f"处理音频数据错误: {e}")

    async def on_conversation_audio_transcript_update(
            self, cli: "AsyncWebsocketsChatClient", event: ConversationAudioTranscriptUpdateEvent
    ):
        log_info(f"语音识别结果: {event.data.content}")

    async def on_conversation_audio_transcript_completed(
            self, cli: AsyncWebsocketsChatClient, event: ConversationAudioTranscriptCompletedEvent
    ):
        try:
            log_info(f"语音识别完成: {event.data.content}")
            self.gui.update_chat_display(event.data.content, is_user=True)
        except Exception as e:
            log_info(f"完成对话错误: {e}")

    async def on_conversation_message_delta(
            self, cli: "AsyncWebsocketsChatClient", event: ConversationMessageDeltaEvent
    ):
        log_info(f"AI回答结果: {event.data.content}")

    async def on_conversation_message_completed(
            self, cli: AsyncWebsocketsChatClient, event: ConversationMessageCompletedEvent
    ):
        try:
            log_info(f"AI回答完成: {event.data.content}")
            self.gui.update_chat_display(event.data.content.strip(), is_user=False)
        except Exception as e:
            log_info(f"完成对话错误: {e}")

    async def on_conversation_chat_completed(
            self, cli: AsyncWebsocketsChatClient, event: ConversationChatCompletedEvent
    ):
        try:
            log_info("接收到服务端一轮文本对话结束消息...")
        except Exception as e:
            log_info(f"完成对话错误: {e}")

    async def on_conversation_audio_completed(
            self, cli: AsyncWebsocketsChatClient, event: ConversationAudioCompletedEvent
    ):
        try:
            log_info("接收到服务端一轮语音对话结束消息...")
            self.first_audio = True

            self.gui.playback_queue.put(None)  # 标记播放结束
        except Exception as e:
            log_info(f"完成对话错误: {e}")

    async def on_conversation_chat_canceled(
            self, cli: AsyncWebsocketsChatClient, event: ConversationChatCanceledEvent
    ):
        try:
            log_info("接收到取消对话消息，清空当前队列数据，停止播放!!!!!")
            self.first_audio = True

            self.gui.update_chat_display("暂停", is_user=True)
            self.gui.end_chat()

        except Exception as e:
            log_info(f"对话打断错误: {e}")


class ModernAudioChatGUI:
    def __init__(self, root):
        self.root = root

        self.p = pyaudio.PyAudio()  # 初始化PyAudio

        self.recording = False
        self.audio_stream: Optional[pyaudio.Stream] = None

        self.is_playing = False
        self.playback_stream = None
        self.playback_queue = queue.Queue()  # 音频播放队列

        self.event_queue = queue.Queue()  # 消息发送队列

        self.setup_gui()  # 创建GUI组件

        coze_api_base = os.getenv("COZE_API_BASE")
        coze_api_base = 'https://10.240.225.61:8000/api/v1/vce/coze'
        coze_api_base = 'https://localhost:8000/api/v1/vce/coze'

        # coze_api_base = 'https://120.92.9.96:9000/api/v1/coze'  # docker
        # coze_api_base = 'https://jiqidpy.local:32075/api/v1/coze'  # k8s ingress(需要配置域名)
        # coze_api_base = 'https://120.92.9.96:30900/api/v1/coze'  # k8s nodeport
        # coze_api_base = 'https://openai.jiqid.net/api/v1/coze'  # k8s ingress Local(域名)

        # coze_api_base = 'https://120.92.9.96:8100/api/v1/coze' # 中文
        # coze_api_base = 'https://120.92.9.96:8200/api/v1/coze' # 英文
        # coze_api_base = 'https://120.92.9.96:8300/api/v1/coze' # 西班牙
        # coze_api_base = 'https://120.92.9.96:8400/api/v1/coze' # 德语

        # coze_api_base = "https://ar.api.jiqid.net/api/v1/coze"
        # coze_api_base = "https://zh.api.jiqid.net/api/v1/coze"
        # coze_api_base = "https://en.api.jiqid.net/api/v1/coze"
        # coze_api_base = "https://es.api.jiqid.net/api/v1/coze"
        # coze_api_base = "https://de.api.jiqid.net/api/v1/coze"
        # coze_api_base = "https://fr.api.jiqid.net/api/v1/coze"
        # coze_api_base = "https://nl.api.jiqid.net/api/v1/coze"
        # coze_api_base = "https://th.api.jiqid.net/api/v1/coze"

        # coze_api_base = "https://haia.dev.cntxt.tools/api/v1/coze"  # english
        # coze_api_base = "https://haia.dev.nrml.tools/api/v1/coze"  # arabic

        token = "jiqid_001"
        # tts_url = "http://localhost:8000/api/v1/coze/v1/chat/tts?token=jiqid_001."

        self.coze = AsyncCoze(auth=TokenAuth(token), base_url=coze_api_base)  # 初始化Coze客户端
        self.chat_client: Optional[AsyncWebsocketsChatClient] = None

        self.loop = asyncio.new_event_loop()  # 创建事件循环

        threading.Thread(target=self.run_async_loop, daemon=True).start()  # 启动异步事件循环
        threading.Thread(target=self.playback_loop, daemon=True).start()  # 启动播放线程

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)  # 添加窗口关闭处理

    def run_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def setup_gui(self):
        self.root.title("智能语音助手")
        self.root.geometry("600x800")  # 设置窗口大小

        style = ttk.Style()  # 设置主题样式
        style.configure("Custom.TButton", padding=10, font=("Helvetica", 12))
        style.configure("Custom.TLabel", font=("Helvetica", 11))

        self.main_frame = ttk.Frame(self.root, padding="20")  # 创建主框架
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.chat_frame = ttk.Frame(self.main_frame)  # 创建聊天记录显示区域
        self.chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        self.chat_display = scrolledtext.ScrolledText(
            self.chat_frame, wrap=tk.WORD, height=20, font=("Helvetica", 11), bg="#f5f5f5"
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        self.status_frame = ttk.Frame(self.main_frame)  # 状态显示区域
        self.status_frame.pack(fill=tk.X, pady=(0, 20))

        self.status_label = ttk.Label(self.status_frame, text="准备就绪", style="Custom.TLabel")
        self.status_label.pack()

        self.volume_bar = ttk.Progressbar(self.status_frame, mode="determinate", length=200)  # 音量指示器
        self.volume_bar.pack(pady=10)

        self.button_frame = ttk.Frame(self.main_frame)  # 按钮控制区域
        self.button_frame.pack(fill=tk.X)

        self.start_button = ttk.Button(
            self.button_frame, text="开启聊天", command=self.start_chat, style="Custom.TButton"
        )  # 开启通话按钮
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.send_button = ttk.Button(
            self.button_frame, text="发送语音", command=self.send_audio, state=tk.DISABLED, style="Custom.TButton"
        )  # 发送数据按钮
        self.send_button.pack(side=tk.LEFT, padx=5)

        self.end_button = ttk.Button(
            self.button_frame, text="结束聊天", command=self.end_chat, state=tk.DISABLED, style="Custom.TButton"
        )  # 结束按钮
        self.end_button.pack(side=tk.LEFT, padx=5)

    def update_chat_display(self, message: str, is_user: bool = True):
        self.chat_display.insert(tk.END,
                                 f"[{datetime.now().strftime('%H:%M:%S')}]: {'我' if is_user else 'AI'}: {message}\n")
        self.chat_display.see(tk.END)  # 自动滚动到底部

    def start_chat(self):
        """ 开启语音 """
        self.start_button.config(state=tk.DISABLED)
        self.send_button.config(state=tk.NORMAL)
        self.end_button.config(state=tk.NORMAL)

        # 启动WebSocket连接
        self.loop.call_soon_threadsafe(self.start_websocket_connection)

        # 开始录音
        self.start_recording()
        self.status_label.config(text="正在录音...")
        self.update_chat_display("开始新的对话", is_user=False)

    def end_chat(self):
        if self.recording:
            self.stop_recording()  # 停止录音

        self.loop.call_soon_threadsafe(self.close_connection)  # 关闭WebSocket连接

        self.start_button.config(state=tk.NORMAL)  # 重置UI
        self.send_button.config(state=tk.DISABLED)
        self.end_button.config(state=tk.DISABLED)
        self.status_label.config(text="准备就绪")
        self.update_chat_display("对话已结束", is_user=False)

        # 清空队列数据
        self.event_queue.queue.clear()
        self.playback_queue.queue.clear()

    def close_connection(self):
        async def close():
            if self.chat_client:
                await self.chat_client.close()
                self.chat_client = None

        asyncio.run_coroutine_threadsafe(close(), self.loop)

    def resume_recording(self):
        """ 重新开始录音 """
        log_info("AI播放5s时间到，开始继续录音")

        self.send_button.config(state=tk.NORMAL)
        self.status_label.config(text="正在录音...")
        self.start_recording()

    def start_recording(self):
        """ 开始录音 """
        try:
            self.recording = True
            self.event_queue.put(
                ChatUpdateEvent.Data.model_validate(
                    {"input_audio": InputAudio.model_validate(
                        {"format": "pcm", "sample_rate": 16000, "channel": CHANNELS,
                         "bit_depth": 16, "codec": "pcm", }), }
                )
            )
            self.audio_stream = self.p.open(
                format=FORMAT,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=int(16000 * INPUT_BLOCK_TIME),  # 计算输入缓冲区大小
                stream_callback=self.audio_callback,
            )  # 打开音频流

        except Exception as e:
            log_info(f"启动录音错误: {e}")
            self.recording = False
            self.status_label.config(text="启动录音失败")
            self.end_chat()

    def audio_callback(self, in_data, frame_count, time_info, status):
        if self.recording:
            try:
                self.event_queue.put(InputAudioBufferAppendEvent.Data.model_validate({"delta": in_data}))
                # 更新音量指示器
                amplitude = max(
                    abs(int.from_bytes(in_data[i: i + 2], "little", signed=True)) for i in range(0, len(in_data), 2)
                )
                volume = min(100, int(amplitude / 32768 * 100))
                self.root.after(0, lambda v=volume: self.volume_bar.configure(value=v))
            except Exception as e:
                log_info(f"录音回调错误: {e}")

        return None, pyaudio.paContinue

    def start_websocket_connection(self):
        async def start():
            kwargs = json.loads(os.getenv("COZE_KWARGS") or "{}")
            self.chat_client = self.coze.websockets.chat.create(
                bot_id=os.getenv("COZE_BOT_ID"),
                on_event=ChatEventHandler(self),
                **kwargs,
            )

            async with self.chat_client() as client:
                while self.chat_client:
                    if not self.event_queue.empty():
                        data = self.event_queue.get()
                        if isinstance(data, ChatUpdateEvent.Data):
                            log_info("发送更新语音播放配置消息")
                            await client.chat_update(data)
                        elif isinstance(data, InputAudioBufferAppendEvent.Data):
                            await client.input_audio_buffer_append(data)
                        else:
                            log_info("发送录音数据发送完毕消息")
                            await client.input_audio_buffer_complete()
                    await asyncio.sleep(0.01)

        asyncio.run_coroutine_threadsafe(start(), self.loop)

    def playback_loop(self):
        """音频播放循环"""
        while True:
            try:
                if self.is_playing:
                    audio_data = self.playback_queue.get()  # 从队列中获取音频数据
                    if audio_data is None:  # None 表示播放结束
                        log_info("接收到语音结束消息，本次语音播放完毕！！！")
                        if self.playback_stream:
                            self.playback_stream.stop_stream()
                            self.playback_stream.close()
                            self.playback_stream = None
                        self.is_playing = False
                        continue

                    if not self.playback_stream:
                        log_info("接收到音频数据，创建播放器！！！")

                        self.playback_stream = self.p.open(
                            format=FORMAT, channels=1, rate=24000, output=True, frames_per_buffer=CHUNK
                        )  # 创建播放流（如果还没有创建）

                    self.playback_stream.write(audio_data)  # 播放音频数据

            except Exception as e:
                log_info(f"播放错误: {e}")
                self.is_playing = False
                if self.playback_stream:
                    try:
                        self.playback_stream.stop_stream()
                        self.playback_stream.close()
                    except Exception as e:
                        pass
                    self.playback_stream = None

            time.sleep(0.01)  # 短暂休眠以避免CPU过载

    def send_audio(self):
        """ 点击发送，并等待数据发送完毕 """
        self.send_button.config(state=tk.DISABLED)  # 禁用发送按钮
        self.status_label.config(text="正在发送...")
        self.loop.call_soon_threadsafe(self.complete_audio)  # 发送完成事件

    def complete_audio(self):
        async def complete():
            self.stop_recording()  # 停止录音，确保消息发送完毕

            while not self.event_queue.empty():
                await asyncio.sleep(0.1)

            if self.chat_client:
                self.event_queue.put(None)  # 发送None消息，表示发送完毕
                await self.chat_client.wait()

        asyncio.run_coroutine_threadsafe(complete(), self.loop)

    def stop_recording(self):
        try:
            self.recording = False
            if self.audio_stream is not None and self.audio_stream.is_active():
                self.audio_stream.stop_stream()
                self.audio_stream.close()
        except Exception as e:
            log_info(f"停止录音错误: {e}")
        finally:
            self.audio_stream = None

    def on_closing(self):
        # 停止录音
        self.stop_recording()

        # 停止播放
        self.is_playing = False
        if self.playback_stream:
            self.playback_stream.stop_stream()
            self.playback_stream.close()

        # 关闭WebSocket连接
        if self.chat_client:
            self.loop.call_soon_threadsafe(self.close_connection)
        # 关闭PyAudio
        if self.p:
            self.p.terminate()
        # 关闭窗口
        self.root.destroy()


def main():
    root = tk.Tk()
    ModernAudioChatGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
