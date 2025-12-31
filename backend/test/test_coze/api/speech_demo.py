# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：speech_demo.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/16 15:33
"""
import asyncio
from backend.common.log import log
from backend.common.infra.openai.speech.speech_coze import open_speech_manager

# submit_to_save = open("test_submit.mp3", "wb")
# query_to_save = open("test_query.mp3", "wb")

mp3_file = open("coze.mp3", "wb")


async def submit_callback(data: bytes | None) -> None:
    if data:
        log.info(f"Received data={len(data)} bytes of audio")
    else:
        log.info(f"Audio stream complete data={data}")


async def submit():
    # Create client
    client = await open_speech_manager.acquire_tts(uid="tts_demo")
    client.set_callback(submit_callback)

    # Submit request
    # task = await client.submit(text="你好，我是波波。")
    # task = await client.submit(text="请问有什么可以帮助的吗？")
    task = await client.query(text="我是一个智能小助手？", is_final=True)
    # task = await client.submit(text="宝贝儿，欢迎收听凯叔讲故事，也感谢你关注凯叔讲故事的微信公众账号。凯叔从今天开始给你讲西游记的故事。西游记是我们中国的4大名着之一，非常有名的一部神话小说，讲的是谁？讲的就是唐朝有一个叫唐三藏的和尚，他要去西天取经，大家也可以叫他唐僧，唐僧可不是一个人在战斗，他有三个徒弟，孙悟空、猪八戒和沙和尚，唐僧带着三个徒弟师徒四人一起去西天取经，在路上遇到了好多的妖魔鬼怪，他们把这些妖魔鬼怪全都打败了，最终取得真经。", is_final=True)

    # When done
    # await client.close()
    await asyncio.sleep(100)  # Non-blocking sleep


async def query_callback(data: bytes | None) -> None:
    if data:
        log.info(f"Received data={len(data)} bytes of audio")
        mp3_file.write(data)
    else:
        log.info(f"Audio stream complete data={data}")
        mp3_file.close()


async def query():
    # Create client
    client = await open_speech_manager.acquire_tts(uid="tts_demo")
    client.set_callback(query_callback)

    # Submit request
    # task = await client.query(text="你好，我是波波。")
    # task = await client.query(text="请问有什么可以帮助的吗？")
    # task = await client.query(text="我是一个智能小助手？", is_final=True)

    task = await client.query(text="我在", is_final=True)
    # task = await client.query(text="联网成功", is_final=True)
    # task = await client.query(text="进入配网模式", is_final=True)

    # task = await client.query(text="切换英文大模型模式", is_final=True)


    # When done
    # await client.close()
    await asyncio.sleep(1000)  # Non-blocking sleep


if __name__ == '__main__':
    # asyncio.run(submit())
    asyncio.run(query())
