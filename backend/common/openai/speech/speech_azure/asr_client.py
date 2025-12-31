# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：asr_client.py
@Author  ：guhua@jiqid.com
@Date    ：2025/06/12 10:25
"""
import asyncio
import traceback

from typing import Callable, Optional

import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech import SpeechRecognizer, SpeechConfig
from azure.cognitiveservices.speech.audio import AudioConfig, PushAudioInputStream

from backend.common.log import log


class WebsocketTextCallback:
    """ 文本内容返回websocket write(azure) -> queue -> ext """

    def __init__(self):
        self._text_callback = None

        self._text_queue = asyncio.Queue(maxsize=1000)

        self._loop = None
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
    def queue_size(self) -> int:
        """获取当前队列大小"""
        return self._text_queue.qsize()

    @property
    def text_callback(self):
        return self._text_callback

    @text_callback.setter
    def text_callback(self, callback):
        self._text_callback = callback

    def _start_send_loop(self) -> None:
        self._send_task = self.loop.create_task(
            self._send_worker(),
        )

    def write(self, text: str) -> int:
        """ speech_azure 回调该方法 """
        self.loop.call_soon_threadsafe(self._text_queue.put_nowait, text)
        return len(text)

    def clear(self):
        """ 清空文本队列并返回清除的消息数量 """
        cleared_count = 0
        try:
            for _ in range(2 * self.queue_size):  # 清空队列
                try:
                    self._text_queue.get_nowait()
                    self._text_queue.task_done()  # 通知队列项已处理
                    cleared_count += 1
                except asyncio.QueueEmpty:
                    break

            log.debug(f"清空队列完成 | 移除消息数: {cleared_count} | "
                      f"当前队列大小: {self._text_queue.qsize()}")
        except Exception as ex:
            log.error(f"队列清空操作异常 - {ex}")

    def close(self) -> None:
        """显式关闭资源"""
        log.debug("ASR处理器关闭, 释放资源...")
        self._send_task.cancel()
        self.clear()

        log.debug("ASR处理器关闭完成")

    async def _send_worker(self):
        while True:
            try:
                # 1. 带超时获取队列数据（避免永久阻塞）
                data = await asyncio.wait_for(
                    self._text_queue.get(),
                    timeout=60.0  # 60秒无新数据则触发超时
                )

                # 2. 检查回调有效性
                if self.text_callback is None:
                    log.debug("文本回调未注册，丢弃数据块")
                    continue

                # 3. 执行回调（捕获回调自身异常）
                try:
                    await self.text_callback(data)
                except Exception as ex:
                    log.error(f"文本回调处理失败 - {ex} - {traceback.format_exc()}")

                # 4. 显式标记任务完成（如果使用join()需要）
                self._text_queue.task_done()

            except asyncio.CancelledError:
                log.info("ASR处理器被终止")
                break
            except asyncio.TimeoutError:
                continue
            except Exception as ex:
                log.critical(f"文本队列处理异常 - {ex} - {traceback.print_exc()}", exc_info=True)
                await asyncio.sleep(1)  # 防止错误导致密集循环


class ASRClient:
    """优化的语音识别(ASR)客户端，支持流式输入和实时回调"""

    def __init__(self, speech_config: SpeechConfig):
        """
        Args:
            speech_config: 语音服务配置
        """
        self.speech_config = speech_config

        self._push_input_stream: Optional[PushAudioInputStream] = None
        self._recognizer: Optional[SpeechRecognizer] = None

        self._text_append_callback: WebsocketTextCallback = WebsocketTextCallback()
        self._text_finish_callback: WebsocketTextCallback = WebsocketTextCallback()

        self.final_text = None  # 最终完整识别文本

        # 事件循环引用
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def loop(self):
        """Lazy initialization of event loop"""
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
        return self._loop

    async def set_uid(self, uid: str):
        pass

    def set_callbacks(self,
                      append_cb: Optional[Callable[[str], None]] = None,
                      finish_cb: Optional[Callable[[str], None]] = None) -> None:
        """设置回调函数

        参数：
            append_cb: 增量识别结果回调（每识别出一部分文本时触发）
            finish_cb: 最终识别结果回调（整句识别完成时触发）
        """
        self._text_append_callback.text_callback = append_cb
        self._text_finish_callback.text_callback = finish_cb

    async def stream_start(self) -> None:
        """ 启动语音识别流
            特性：
            1. 确保每次都是全新会话
        """
        self._init_recognizer()  # 每次重新开始识别时初始化，确保每次识别都是新的，不会因为上次识别结果导致下次识别结果错误。

        self.final_text = ''
        self.start_recognition()

    async def stream_append(self, audio_chunk: bytes) -> None:
        """
        安全追加音频数据到识别流

        Args:
            audio_chunk: 要追加的音频数据块（建议10-50ms长度的PCM数据）
        """
        self._push_input_stream.write(audio_chunk)

    async def stream_finish(self) -> None:
        """ 安全结束语音识别流"""
        self.stop_recognition()  # 通知azure，本次语音内容发送结束

        # stop_at = self.loop.time()
        # while self.final_text is not None and self.loop.time() - stop_at < 30.0:  # 30秒超时 TODO
        #     await asyncio.sleep(.1)
        #
        # latency = self.loop.time() - stop_at
        # log.debug(f"ASR识别完成, 耗时：{latency * 1000:.2f}ms")

    def _init_recognizer(self):
        """初始化语音识别器"""
        # 1. 初始化音频流
        self._push_input_stream = PushAudioInputStream()
        self._recognizer = SpeechRecognizer(
            speech_config=self.speech_config,
            audio_config=AudioConfig(stream=self._push_input_stream))

        # 2. 注册回调
        self._recognizer.recognized.connect(self._recognized_callback)
        self._recognizer.session_stopped.connect(self._session_stopped_callback)
        self._recognizer.canceled.connect(self._canceled_callback)

        self._text_append_callback.clear()
        self._text_finish_callback.clear()

    def _recognized_callback(self, evt) -> None:
        """识别成功回调"""
        log.debug(f"识别中，识别结果: {evt.result.text}")
        if evt.result.text:
            self.final_text += evt.result.text
            self._text_append_callback.write(self.final_text)

    def _session_stopped_callback(self, evt) -> None:
        """会话停止回调"""
        log.debug(f"识别停止，识别结果: {self.final_text}")
        self._text_finish_callback.write(self.final_text)
        self.final_text = None

    def _canceled_callback(self, evt) -> None:
        """识别取消回调"""
        log.warning(f"识别被取消: 原因={evt.reason}")
        if evt.reason == speechsdk.CancellationReason.Error:
            log.error(f"错误详情: {evt.error_details}")
        self.final_text = None

    def start_recognition(self) -> None:
        """启动连续语音识别"""
        try:
            self._recognizer.start_continuous_recognition_async()
        except Exception as e:
            log.error(f"启动识别失败 - {e}")
            raise

    def stop_recognition(self) -> None:
        """停止连续语音识别"""
        try:
            if self._push_input_stream is not None:
                self._push_input_stream.close()  # 关闭输入流，否则会等待10秒
            if self._recognizer is not None:
                self._recognizer.stop_continuous_recognition_async()
        except Exception as e:
            log.error(f"停止识别失败 - {e}")
            raise

    async def close(self) -> None:
        """完全释放资源"""
        try:
            self.stop_recognition()
            self._text_append_callback.close()
            self._text_finish_callback.close()
            log.debug("ASR语音服务资源已释放")
        except Exception as e:
            log.error(f"ASR资源释放失败 - {e}")

    async def __aenter__(self):
        """进入上下文时初始化资源"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时清理资源"""
        await self.close()
