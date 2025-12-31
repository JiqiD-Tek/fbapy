# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：transcriptions_demo.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/16 15:34
"""
import asyncio
from backend.common.log import log
from backend.common.infra.openai.speech.speech_coze import open_speech_manager


async def on_text_callback(text: str):
    log.info(text)


async def demo():
    audio_path = "input.wav"
    with open(audio_path, mode="rb") as _f:
        audio_data = _f.read()

    client = await open_speech_manager.acquire_asr(uid="asr_demo")

    client.set_callbacks(
        append_cb=on_text_callback,
        finish_cb=on_text_callback
    )

    async def _trans():
        log.info("start")
        await client.stream_start()

        offset = 0
        while offset < len(audio_data):
            audio_chunk = audio_data[offset:offset + 10000]
            await client.stream_append(audio_chunk=audio_chunk)
            offset += 10000

        await client.stream_finish()

    await _trans()
    await asyncio.sleep(1)
    await _trans()

    # await client.close()
    await asyncio.sleep(10)


if __name__ == '__main__':
    asyncio.run(demo())
