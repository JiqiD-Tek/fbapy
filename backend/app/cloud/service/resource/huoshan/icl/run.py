# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : run.py
@Author  : guhua@jiqid.com
@Date    : 2026/11/25 20:24
"""

import base64
import json
import time
import uuid
from typing import Any, Optional

import requests

# ========== 1) 接口地址（一般不用改） ==========
VOICE_CLONE_URL = "https://openspeech.bytedance.com/api/v3/tts/voice_clone"
GET_VOICE_URL = "https://openspeech.bytedance.com/api/v3/tts/get_voice"
TTS_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"

# 训练状态枚举
STATUS_NOT_FOUND = 0
STATUS_TRAINING = 1
STATUS_SUCCESS = 2
STATUS_FAILED = 3
STATUS_ACTIVE = 4
READY_STATUSES = (STATUS_SUCCESS, STATUS_ACTIVE)


# ========== 2) 工具函数 ==========
def build_headers(api_key: str) -> dict:
    return {
        "Content-Type": "application/json",
        "X-Api-Key": api_key,
        "X-Api-Request-Id": str(uuid.uuid4()),
    }


def file_to_base64(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def post_json(url: str, payload: dict, api_key: str, tag: str) -> dict:
    """统一的 POST + JSON 解析 + 日志。"""
    resp = requests.post(url, headers=build_headers(api_key), data=json.dumps(payload), timeout=60)
    print(f"[{tag}] status_code = {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        print(resp.text)
        raise
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return data


# ========== 3) 训练 / 查询 ==========
def train_voice_clone(
    api_key: str,
    speaker_id: str,
    audio_path: str,
    audio_format: str,
    language: int,
    demo_text: str,
    custom_speaker_id: Optional[str] = None,
) -> dict:
    payload: dict[str, Any] = {
        "speaker_id": "custom_speaker_id" if custom_speaker_id else speaker_id,
        "audio": {
            "data": file_to_base64(audio_path),
            "format": audio_format,
        },
        "language": language,
        "extra_params": {
            # 训练音频本身质量好时建议关闭降噪，避免损失细节
            "enable_audio_denoise": False,
            # 开启音源分离，适合有轻微背景音时；干净录音可不开
            "voice_clone_enable_mss": False,
            # ASR 截断，避免字被截断；可按需开启
            "enable_crop_by_asr": True,
            # 质量检测会降低复刻成功率，训练初期可先不开
            "enable_check_prompt_text_quality": False,
            "enable_check_audio_quality": False,
            # 试听文本（不参与训练，只用于生成试听音频）
            "demo_text": demo_text,
        },
    }

    if custom_speaker_id:
        payload["custom_speaker_id"] = custom_speaker_id

    return post_json(VOICE_CLONE_URL, payload, api_key, tag="train_voice_clone")


def get_voice_status(
    api_key: str,
    speaker_id: str,
    custom_speaker_id: Optional[str] = None,
) -> dict:
    payload: dict[str, Any] = {
        "speaker_id": "custom_speaker_id" if custom_speaker_id else speaker_id,
    }
    if custom_speaker_id:
        payload["custom_speaker_id"] = custom_speaker_id

    return post_json(GET_VOICE_URL, payload, api_key, tag="get_voice_status")


def wait_until_ready(
    api_key: str,
    speaker_id: str,
    custom_speaker_id: Optional[str] = None,
    poll_interval: int = 5,
    timeout: int = 180,
) -> dict:
    start = time.time()
    while True:
        data = get_voice_status(api_key, speaker_id, custom_speaker_id)
        status = data.get("status")

        if status in READY_STATUSES:
            print("[wait_until_ready] 音色可用")
            return data
        if status == STATUS_FAILED:
            raise RuntimeError(
                "音色训练失败：\n" + json.dumps(data, ensure_ascii=False, indent=2)
            )
        if time.time() - start > timeout:
            raise TimeoutError("等待训练超时，请稍后再查状态")

        print(f"[wait_until_ready] 训练中，{poll_interval} 秒后重试...")
        time.sleep(poll_interval)


# ========== 4) 合成（单向流式 HTTP Chunked，逐行 JSON + Base64 拼接） ==========
def synthesize(
    api_key: str,
    speaker_id: str,
    text: str,
    output_path: str,
    custom_speaker_id: Optional[str] = None,
    audio_format: str = "wav",
    sample_rate: int = 24000,
) -> None:
    payload = {
        "user": {"uid": str(uuid.uuid4())},
        "req_params": {
            "text": text,
            "speaker": "custom_speaker_id" if custom_speaker_id else speaker_id,
            "audio_params": {"format": audio_format, "sample_rate": sample_rate},
        },
    }
    if custom_speaker_id:
        payload["req_params"]["custom_speaker_id"] = custom_speaker_id

    headers = build_headers(api_key)
    # 复刻音色必须指定资源 ID，否则 403
    headers["X-Api-Resource-Id"] = "seed-icl-2.0"

    with requests.post(TTS_URL, headers=headers, data=json.dumps(payload), stream=True, timeout=120) as resp:
        print(f"[synthesize] status_code = {resp.status_code}")
        resp.raise_for_status()

        with open(output_path, "wb") as f:
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    print("[synthesize] 跳过非 JSON 行:", line[:120])
                    continue

                if obj.get("code") == 20000000:
                    print("[synthesize] 合成正常结束")
                    break

                if obj.get("code") != 0:
                    raise RuntimeError(f"合成失败: {json.dumps(obj, ensure_ascii=False)}")

                b64 = obj.get("data")
                if b64:
                    f.write(base64.b64decode(b64))
    print(f"[synthesize] 已保存到 {output_path}")


# ========== 5) 主流程（调试主要改这里） ==========
def main() -> None:
    # ---- 调试参数，全部集中在这里 ----
    api_key = "5aadc376-4432-4462-945a-76d3ea532e4e"
    api_key = "d7109a24-08ed-456c-8dc9-288367c8b0ca"  # JS61

    # 预付费音色：填控制台购买的 SpeakerID，例如 "S_J6luyDOZ1"
    # 后付费音色：speaker_id 固定填 "custom_speaker_id"，并设置 custom_speaker_id
    speaker_id = "S_bpthyDOZ1"
    custom_speaker_id = None  # 例如 "bilingual_pax_001"，仅后付费时使用

    audio_path = "audio/唐僧2.mp3"
    audio_format = "mp3"

    # language: 0 = 中文（默认），1 = 英文
    language = 0

    demo_text_cn = "欢迎来到语音演示，这是一段用于测试自定义音色的中文试听文本。"
    demo_text_en = "Welcome to the voice demo. This is an English test sentence for custom speaker synthesis."
    demo_text = demo_text_en if language == 1 else demo_text_cn

    synth_text = (
        "你好，这是中文测试。"
        "Hello, this is an English test. "
        "Let us check bilingual pronunciation."
    )
    output_wav = "output_seed_icl_2.wav"

    # ---- 第一步：训练/注册音色 ----
    train_voice_clone(
        api_key=api_key,
        speaker_id=speaker_id,
        audio_path=audio_path,
        audio_format=audio_format,
        language=language,
        demo_text=demo_text,
        custom_speaker_id=custom_speaker_id,
    )

    # ---- 第二步：等待训练成功 ----
    voice_info = wait_until_ready(
        api_key=api_key,
        speaker_id=speaker_id,
        custom_speaker_id=custom_speaker_id,
        poll_interval=5,
        timeout=180,
    )

    print("[speaker_status]")
    print(json.dumps(voice_info.get("speaker_status", []), ensure_ascii=False, indent=2))

    # ---- 第三步：用复刻音色合成 ----
    synthesize(
        api_key=api_key,
        speaker_id=speaker_id,
        text=synth_text,
        output_path=output_wav,
        custom_speaker_id=custom_speaker_id,
        audio_format="wav",
        sample_rate=24000,
    )


if __name__ == "__main__":
    main()