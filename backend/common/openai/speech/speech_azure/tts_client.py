# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：tts_client.py
@Author  ：guhua@jiqid.com
@Date    ：2025/06/12 10:26
"""

import asyncio
import traceback

from typing import Callable, Optional

import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer
from azure.cognitiveservices.speech.audio import AudioOutputConfig, PushAudioOutputStream, PushAudioOutputStreamCallback

from backend.common.log import log
from backend.common.openai.speech.base.tts import TTS
from backend.common.openai.speech.base.tts_cache import TTSCache


class WebsocketStreamCallback(PushAudioOutputStreamCallback):
    """ 语音内容返回websocket write(azure) -> queue -> ext """

    def __init__(self):

        self._audio_callback = None

        self._audio_queue = asyncio.Queue(maxsize=1000)

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._send_task: Optional[asyncio.Task] = None
        self._start_send_loop()

    @property
    def loop(self):
        """Lazy initialization of event loop"""
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
        return self._loop

    @property
    def audio_callback(self):
        return self._audio_callback

    @audio_callback.setter
    def audio_callback(self, callback):
        self._audio_callback = callback

    def _start_send_loop(self) -> None:
        self._send_task = self.loop.create_task(
            self._send_worker(),
        )

    def write(self, audio_buffer: memoryview) -> int:
        """ speech_azure 回调该方法 """
        self.loop.call_soon_threadsafe(self._audio_queue.put_nowait, audio_buffer.tobytes())
        return audio_buffer.nbytes

    def close(self) -> None:
        """显式关闭资源"""
        log.debug("TTS异步处理器关闭, 释放资源...")
        self._send_task.cancel()  # 取消发送任务

        while not self._audio_queue.empty():  # 清空队列
            try:
                self._audio_queue.get_nowait()
                self._audio_queue.task_done()  # 通知队列项已处理
            except asyncio.QueueEmpty:
                break
        log.info("TTS异步处理器关闭完成")

    async def _send_worker(self):
        while True:
            try:
                # 1. 安全获取队列数据（60秒超时防止永久阻塞）
                audio_chunk = await asyncio.wait_for(
                    self._audio_queue.get(),
                    timeout=60.0
                )

                # 2. 检查回调有效性
                if not self.audio_callback:
                    log.debug("音频回调未注册，丢弃数据块")
                    continue

                # 3. 执行回调（隔离回调异常）
                try:
                    await self.audio_callback(audio_chunk)
                except Exception as ex:
                    log.error(f"音频回调执行失败 - {ex} - {traceback.format_exc()}")

                # 4. 标记任务完成（支持队列join同步）
                self._audio_queue.task_done()

            except asyncio.CancelledError:
                log.info("TTS异步处理器被终止")
                break
            except asyncio.TimeoutError:
                continue
            except Exception as ex:
                log.critical(f"音频流处理错误 - {ex} - {traceback.print_exc()}", exc_info=True)
                await asyncio.sleep(1)  # 避免错误循环占用CPU


class TTSClient(TTS):
    """ tts 合成器 """

    def __init__(self, speech_config: SpeechConfig):
        self._push_output_stream_callback = WebsocketStreamCallback()
        self._push_output_stream = PushAudioOutputStream(self._push_output_stream_callback)
        self._synthesizer = SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=AudioOutputConfig(stream=self._push_output_stream))

        self._register_synthesizer_callbacks()


        # 合成任务队列（带背压控制）
        self._tts_queue = asyncio.Queue(maxsize=1000)
        # 音频缓存系统
        self._tts_cache = TTSCache(maxsize=10, ttl=3600)

        # 事件循环引用
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._tts_task: Optional[asyncio.Task] = None
        self.start_tts_task()

    @property
    def loop(self):
        """Lazy initialization of event loop"""
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
        return self._loop

    def start_tts_task(self) -> None:
        """ 启动合成任务 """
        self._tts_task = self.loop.create_task(
            self._tts_worker(),
            name=f"TTSWorker-{id(self)}"
        )

    @property
    def tts_cache(self) -> Optional[TTSCache]:
        return self._tts_cache

    async def set_uid(self, uid: str):
        pass

    def set_callback(self, callback: Optional[Callable[[bytes], None]] = None):
        """ 生成的数据通过回调发送给客户端 """
        self._push_output_stream_callback.audio_callback = callback  # 生成的数据通过回调发送给客户端

    async def submit(self, text: str, is_final: bool = False) -> None:
        log.debug(f"提交TTS submit合成请求: [text={text} | size={len(text)} | is_final={is_final}]")
        self._synthesizer.speak_text_async(text)

    async def query(self, text: str, is_final: bool = False) -> None:
        log.debug(f"提交TTS query合成请求: [text={text} | size={len(text)} | is_final={is_final}]")
        self.loop.call_soon_threadsafe(self._tts_queue.put_nowait, (text, is_final))

    def stop_speaking(self):
        log.debug("停止语音合成")
        self._synthesizer.stop_speaking_async()

    def _register_synthesizer_callbacks(self):
        """注册语音生成事件回调"""
        self._synthesizer.synthesis_completed.connect(self._on_synthesis_completed)  # 注册合成完成事件
        self._synthesizer.synthesis_canceled.connect(self._on_synthesis_cancel)  # 注册合成取消事件

    def _on_synthesis_completed(self, evt: speechsdk.SessionEventArgs):
        log.debug(f"语音合成完成: {evt}")

    def _on_synthesis_cancel(self, evt: speechsdk.SessionEventArgs):
        log.debug(f"语音合成取消: {evt}")

    async def close(self):
        try:
            self.stop_speaking()
            self._push_output_stream_callback.close()
            log.debug("TTS语音服务资源已释放")
        except Exception as e:
            log.error(f"TTS资源释放失败: {type(e).__name__}: {e}")

        log.debug("TTS处理器关闭, 释放资源...")
        self._tts_task.cancel()
        while not self._tts_queue.empty():  # 清空队列
            try:
                self._tts_queue.get_nowait()
                self._tts_queue.task_done()  # 通知队列项已处理
            except asyncio.QueueEmpty:
                break

        await self._tts_cache.close()
        log.info("TTS处理器关闭完成")

    async def __aenter__(self):
        """进入上下文时初始化资源"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时清理资源"""
        await self.close()

    async def _tts_worker(self):
        while True:
            try:
                # 1. 安全获取队列任务（带超时防止永久阻塞）
                text, is_final = await asyncio.wait_for(
                    self._tts_queue.get(),
                    timeout=60.0
                )

                # 2. 处理请求
                try:
                    future = self._synthesizer.speak_text_async(text)
                    if is_final:
                        await self.loop.run_in_executor(
                            None,
                            lambda: (future.get(), self._push_output_stream_callback.write(memoryview(b'')))  # 发送结束标记
                        )  # 在线程池中等待
                finally:
                    # 3. 标记任务完成（支持队列join同步）
                    self._tts_queue.task_done()
                    await asyncio.sleep(.1)  # 每次都是异步(延长100ms 保证识别顺序)

            except asyncio.CancelledError:
                log.info("TTS处理器被终止")
                break
            except asyncio.TimeoutError:
                continue
            except Exception as ex:
                log.critical(f"TTS处理器发生未捕获异常 - {ex} - {traceback.print_exc()}", exc_info=True)
                await asyncio.sleep(1)  # 避免错误循环占用CPU
