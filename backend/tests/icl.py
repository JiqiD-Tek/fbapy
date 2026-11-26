# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : icl.py
@Author  : guhua@jiqid.com
@Date    : 2026/11/25 20:24
"""
import base64
import json
import time
import uuid
import requests


# ========== 1) 改成你自己的参数 ==========
API_KEY = "d7109a24-08ed-456c-8dc9-288367c8b0ca"

# 预付费音色：填控制台购买的 SpeakerID，例如 "S_J6luyDOZ1"
# 后付费音色：这里 speaker_id 固定填 "custom_speaker_id"，并设置 CUSTOM_SPEAKER_ID
SPEAKER_ID = "S_J6luyDOZ1"
CUSTOM_SPEAKER_ID = None   # 例如 "bilingual_pax_001"，仅后付费时使用

AUDIO_PATH = "prompt.wav"   # 你的训练音频，建议 wav，14~30秒，包含中英双语
AUDIO_FORMAT = "wav"

# language:
# 0 = 中文（默认）
# 1 = 英文
# 如果你主业务是中文，但训练音频包含中英双语，建议先试 0；主业务是英文则试 1
LANGUAGE = 0

# demo_text 建议和 language 保持一致
# language=0 就传中文试听文本；language=1 就传英文试听文本
DEMO_TEXT_CN = "欢迎来到语音演示，这是一段用于测试自定义音色的中文试听文本。"
DEMO_TEXT_EN = "Welcome to the voice demo. This is an English test sentence for custom speaker synthesis."

# 合成参数
SYNTH_TEXT = "你好，这是中文测试。Hello, this is an English test. Let us check bilingual pronunciation."
OUTPUT_WAV = "output_seed_icl_2.wav"


# ========== 2) 公共配置 ==========
VOICE_CLONE_URL = "https://openspeech.bytedance.com/api/v3/tts/voice_clone"
GET_VOICE_URL = "https://openspeech.bytedance.com/api/v3/tts/get_voice"

# 复刻音色合成走单向流式 HTTP Chunked 接口
TTS_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"

HEADERS = {
    "Content-Type": "application/json",
    "X-Api-Key": API_KEY,
}


def file_to_base64(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def build_demo_text(language: int) -> str:
    if language == 0:
        return DEMO_TEXT_CN
    elif language == 1:
        return DEMO_TEXT_EN
    else:
        return DEMO_TEXT_CN


# ========== 3) V3 训练接口：注册/训练音色 ==========
def train_voice_clone():
    payload = {
        "speaker_id": CUSTOM_SPEAKER_ID if CUSTOM_SPEAKER_ID else SPEAKER_ID,
        "audio": {
            "data": file_to_base64(AUDIO_PATH),
            "format": AUDIO_FORMAT,
        },
        "language": LANGUAGE,
        "extra_params": {
            # 训练音频本身质量好时建议关闭降噪，避免损失细节
            "enable_audio_denoise": False,

            # 音频噪声明显时可改成 True
            # "enable_audio_denoise": True,

            # 开启音源分离，适合有轻微背景音时；干净录音可不开
            "voice_clone_enable_mss": False,

            # ASR 截断，避免字被截断；可按需开启
            "enable_crop_by_asr": True,

            # 质量检测会降低复刻成功率，训练初期可先不开
            "enable_check_prompt_text_quality": False,
            "enable_check_audio_quality": False,

            # 试听文本
            "demo_text": build_demo_text(LANGUAGE),
        }
    }

    if CUSTOM_SPEAKER_ID:
        payload["speaker_id"] = "custom_speaker_id"
        payload["custom_speaker_id"] = CUSTOM_SPEAKER_ID

    headers = dict(HEADERS)
    headers["X-Api-Request-Id"] = str(uuid.uuid4())

    resp = requests.post(VOICE_CLONE_URL, headers=headers, data=json.dumps(payload))
    print("[train_voice_clone] status_code =", resp.status_code)

    try:
        data = resp.json()
    except Exception:
        print(resp.text)
        raise

    print(json.dumps(data, ensure_ascii=False, indent=2))
    return data


# ========== 4) 查询训练状态 ==========
def get_voice_status(speaker_id: str, custom_speaker_id: str = None):
    payload = {
        "speaker_id": "custom_speaker_id" if custom_speaker_id else speaker_id,
    }
    if custom_speaker_id:
        payload["custom_speaker_id"] = custom_speaker_id

    headers = dict(HEADERS)
    headers["X-Api-Request-Id"] = str(uuid.uuid4())

    resp = requests.post(GET_VOICE_URL, headers=headers, data=json.dumps(payload))
    print("[get_voice_status] status_code =", resp.status_code)

    try:
        data = resp.json()
    except Exception:
        print(resp.text)
        raise

    print(json.dumps(data, ensure_ascii=False, indent=2))
    return data


def wait_until_ready(speaker_id: str, custom_speaker_id: str = None, poll_interval: int = 5, timeout: int = 180):
    """
    status:
    0 = NotFound
    1 = Training
    2 = Success
    3 = Failed
    4 = Active
    """
    start = time.time()
    while True:
        data = get_voice_status(speaker_id, custom_speaker_id)
        status = data.get("status")

        if status in (2, 4):
            print("[wait_until_ready] 音色可用")
            return data
        if status == 3:
            raise RuntimeError("音色训练失败：\n" + json.dumps(data, ensure_ascii=False, indent=2))

        if time.time() - start > timeout:
            raise TimeoutError("等待训练超时，请稍后再查状态")

        print(f"[wait_until_ready] 训练中，{poll_interval} 秒后重试...")
        time.sleep(poll_interval)


# ========== 5) 用复刻 2.0 合成音频 ==========
def tts_with_clone_2(speaker_id: str, text: str, output_path: str, custom_speaker_id: str = None):
    """
    使用复刻 2.0 资源合成：
    - Resource-Id: seed-icl-2.0
    - speaker: 你的复刻音色ID
    - model_type: 2.0 一般传 4 或 5；你账号里很多 2.0 音色实际返回 model_type=5
    """
    real_speaker_id = custom_speaker_id if custom_speaker_id else speaker_id

    payload = {
        "user": {
            "uid": "python_demo_user"
        },
        "event": "finish",
        "namespace": "volcano_icl",   # 复刻音色使用 volcano_icl；不要和 volcano_tts 混用
        "payload": {
            "speaker": real_speaker_id,
            "text": text,
            "model_type": 5,           # 2.0 常见值；如效果不对可试 4
            "audio_params": {
                "format": "wav",
                "sample_rate": 24000
            }
        }
    }

    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": API_KEY,
        "X-Api-Resource-Id": "seed-icl-2.0",
        "X-Api-Request-Id": str(uuid.uuid4()),
    }

    resp = requests.post(TTS_URL, headers=headers, data=json.dumps(payload), stream=True)
    print("[tts_with_clone_2] status_code =", resp.status_code)

    if resp.status_code != 200:
        print(resp.text)
        resp.raise_for_status()

    # HTTP Chunked 返回音频二进制流，直接落盘
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)

    print(f"[tts_with_clone_2] 合成完成，已保存到: {output_path}")


# ========== 6) 主流程 ==========
if __name__ == "__main__":
    # 第一步：训练/注册音色
    train_resp = train_voice_clone()

    # 第二步：等待训练成功
    voice_info = wait_until_ready(SPEAKER_ID, CUSTOM_SPEAKER_ID)

    # 打印返回的 model_type，确认 1.0/2.0 都有哪些能力
    speaker_status = voice_info.get("speaker_status", [])
    print("[speaker_status]")
    print(json.dumps(speaker_status, ensure_ascii=False, indent=2))

    # 第三步：用 2.0 资源合成
    tts_with_clone_2(
        speaker_id=SPEAKER_ID,
        custom_speaker_id=CUSTOM_SPEAKER_ID,
        text=SYNTH_TEXT,
        output_path=OUTPUT_WAV
    )