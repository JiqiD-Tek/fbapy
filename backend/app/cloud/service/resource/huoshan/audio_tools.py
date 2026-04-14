# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : audio_tools.py
@Author  : OpenAI
@Date    : 2026/04/13
"""

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
        raise ValueError(f'speech audio does not exist: {speech_path}')
    if bgm_volume < 0:
        raise ValueError('bgm_volume cannot be less than 0')
    if not _is_remote_media_source(background_url):
        raise ValueError(f'background audio URL is invalid: {background_url}')

    ffmpeg_path = _resolve_ffmpeg_executable()
    speech_duration = _probe_duration_seconds(ffmpeg_path, speech_path)
    fade_out_start = max(0.0, speech_duration - fade_out_seconds)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_path,
        '-y',
        '-v',
        'error',
        '-i',
        str(speech_path),
        '-stream_loop',
        '-1',
        '-i',
        background_url,
        '-filter_complex',
        (
            '[1:a]volume={0:.3f},'
            'afade=t=in:st=0:d={1:.3f},'
            'afade=t=out:st={2:.3f}:d={3:.3f}[bg];'
            '[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]'
        ).format(
            bgm_volume,
            max(0.0, fade_in_seconds),
            fade_out_start,
            max(0.0, fade_out_seconds),
        ),
        '-map',
        '[aout]',
        '-c:a',
        'libmp3lame',
        '-b:a',
        '128k',
        str(output_path),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode('utf-8', errors='replace').strip()
        raise RuntimeError(f'background audio mixing failed: {detail or output_path}') from exc

    return 'ffmpeg-amix'


def _is_remote_media_source(source: str) -> bool:
    return urlparse(source).scheme in {'http', 'https'}


def _resolve_ffmpeg_executable() -> str:
    system_ffmpeg = shutil.which('ffmpeg')
    if system_ffmpeg:
        return system_ffmpeg

    try:
        from imageio_ffmpeg import get_ffmpeg_exe
    except ImportError as exc:
        raise RuntimeError('mixing background audio requires ffmpeg or imageio-ffmpeg') from exc

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
