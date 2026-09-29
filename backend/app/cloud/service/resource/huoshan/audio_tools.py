# -*- coding: UTF-8 -*-
"""火山故事音频处理工具。"""

from __future__ import annotations

import shutil
import subprocess

from pathlib import Path
from urllib.parse import urlparse


def mix_audio_with_bgm(
        speech_path: Path,
        background_url: str,
        output_path: Path,
        *,
        bgm_volume: float = 0.5,
        fade_in_seconds: float = 2.0,
        fade_out_seconds: float = 4.0,
) -> str:
    if not speech_path.exists():
        raise ValueError(f'语音文件不存在：{speech_path}')
    if bgm_volume < 0:
        raise ValueError('背景音乐音量不能小于 0')
    if urlparse(background_url).scheme not in {'http', 'https'}:
        raise ValueError(f'背景音乐地址无效：{background_url}')

    ffmpeg_path = _resolve_ffmpeg_executable()
    speech_duration = _probe_duration_seconds(ffmpeg_path, speech_path)
    fade_out_start = max(0.0, speech_duration - fade_out_seconds)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_path, '-y', '-v', 'error', '-i', str(speech_path),
        '-stream_loop', '-1', '-i', background_url, '-filter_complex',
        ('[1:a]volume={0:.3f},afade=t=in:st=0:d={1:.3f},'
         'afade=t=out:st={2:.3f}:d={3:.3f}[bg];'
         '[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]').format(
             bgm_volume, max(0.0, fade_in_seconds), fade_out_start, max(0.0, fade_out_seconds),
         ),
        '-map', '[aout]', '-c:a', 'libmp3lame', '-b:a', '128k', str(output_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode('utf-8', errors='replace').strip()
        raise RuntimeError(f'背景音乐混音失败：{detail or output_path}') from exc
    return 'ffmpeg-amix'


def _resolve_ffmpeg_executable() -> str:
    system_ffmpeg = shutil.which('ffmpeg')
    if system_ffmpeg:
        return system_ffmpeg

    try:
        from imageio_ffmpeg import get_ffmpeg_exe
    except ImportError as exc:
        raise RuntimeError('背景音乐混音需要 ffmpeg 或 imageio-ffmpeg') from exc

    return get_ffmpeg_exe()


def _probe_duration_seconds(ffmpeg_path: str, path: Path) -> float:
    command = [
        ffmpeg_path,
        '-v',
        'info',
        '-i',
        str(path),
        '-f',
        'null',
        '-',
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    stderr = completed.stderr or ''
    marker = 'Duration: '
    start = stderr.find(marker)
    if start < 0:
        return 0.0

    raw = stderr[start + len(marker):].split(',', 1)[0].strip()
    parts = raw.split(':')
    if len(parts) != 3:
        return 0.0

    try:
        hours = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
    except ValueError:
        return 0.0

    return hours * 3600.0 + minutes * 60.0 + seconds


def probe_audio_duration(path: Path) -> float:
    """获取音频文件时长，单位为秒。"""
    return _probe_duration_seconds(_resolve_ffmpeg_executable(), path)


def concatenate_audio_segments(segment_paths: list[Path], output_path: Path) -> None:
    """在不重新编码的情况下合并多个 MP3 音频片段。"""
    if not segment_paths:
        raise ValueError('至少需要一个音频片段')
    if any(not path.exists() for path in segment_paths):
        raise ValueError('所有音频片段都必须存在')

    ffmpeg_path = _resolve_ffmpeg_executable()
    concat_file = output_path.with_suffix('.concat.txt')
    concat_lines = []
    for path in segment_paths:
        escaped_path = path.resolve().as_posix().replace("'", "'\\''")
        concat_lines.append(f"file '{escaped_path}'\n")
    concat_file.write_text(''.join(concat_lines), encoding='utf-8')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        command = [
            ffmpeg_path,
            '-y',
            '-v',
            'error',
            '-f',
            'concat',
            '-safe',
            '0',
            '-i',
            str(concat_file),
            '-c',
            'copy',
            str(output_path),
        ]
        subprocess.run(
            command,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode('utf-8', errors='replace').strip()
        raise RuntimeError(f'音频合并失败：{detail or output_path}') from exc
    finally:
        concat_file.unlink(missing_ok=True)
