from __future__ import annotations

import json
import subprocess
import tempfile

from pathlib import Path
from typing import Optional, Sequence, TypedDict

from backend.app.cloud.service.resource.providers.led.ledword.core import BOARD_HEIGHT, BOARD_WIDTH
from backend.tests.led.preview_renderer import FrameGrid, FrameSequence


class AudioInputFrame(TypedDict, total=False):
    energy: float
    bass: float
    mid: float
    high: float
    onset: float


RUNNER_SCRIPT = """const fs = require("fs");
const vm = require("vm");

const functionPath = process.argv[2];
const audioPath = process.argv[3];
const code = fs.readFileSync(functionPath, "utf8");
const audioFrames = JSON.parse(fs.readFileSync(audioPath, "utf8"));
const sandbox = { Math, Number, Array, JSON };

vm.createContext(sandbox);
vm.runInContext(
  code + "\\nif (typeof renderFrame !== 'function') { throw new Error('renderFrame is not defined'); } this.__renderFrame__ = renderFrame;",
  sandbox
);

const frames = [];
for (const audio of audioFrames) {
  frames.push(sandbox.__renderFrame__(audio));
}

process.stdout.write(JSON.stringify({ frames }));
"""


def render_frames_with_node(
    *,
    audio_frames: Sequence[AudioInputFrame],
    function_path: Optional[Path] = None,
    function_code: Optional[str] = None,
) -> FrameSequence:
    if function_path is None and not function_code:
        raise ValueError('either function_path or function_code is required')
    if function_path is not None and not function_path.exists():
        raise ValueError(f'function file does not exist: {function_path}')
    if not audio_frames:
        raise ValueError('audio_frames must not be empty')

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        runner_path = temp_dir / 'runner.js'
        audio_path = temp_dir / 'audio.json'
        runtime_function_path = function_path
        if function_code:
            runtime_function_path = temp_dir / 'function.js'
            runtime_function_path.write_text(function_code.rstrip() + '\n', encoding='utf-8')
        runner_path.write_text(RUNNER_SCRIPT, encoding='utf-8')
        audio_path.write_text(json.dumps(list(audio_frames)), encoding='utf-8')

        try:
            completed = subprocess.run(
                ['node', str(runner_path), str(runtime_function_path), str(audio_path)],
                check=True,
                capture_output=True,
                encoding='utf-8',
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Node.js executable 'node' was not found") from exc
        except subprocess.CalledProcessError as exc:
            error_text = exc.stderr.strip() or exc.stdout.strip()
            raise RuntimeError(f'Node preview execution failed: {error_text}') from exc

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError('Node preview output is not valid JSON') from exc

    frames = payload.get('frames')
    if not isinstance(frames, list) or not frames:
        raise ValueError('Node preview output does not contain valid frames')

    validated_frames: FrameSequence = []
    for index, frame in enumerate(frames):
        validated_frames.append(_normalize_frame(frame, frame_index=index))
    return validated_frames


def _normalize_frame(frame, *, frame_index: int) -> FrameGrid:
    normalized_input = _unwrap_frame_payload(frame)
    if not isinstance(normalized_input, list) or len(normalized_input) != BOARD_HEIGHT:
        raise ValueError(f'frames[{frame_index}] row count must be {BOARD_HEIGHT}')

    normalized_rows: FrameGrid = []
    for row_index, row in enumerate(normalized_input):
        if not isinstance(row, list) or len(row) != BOARD_WIDTH:
            raise ValueError(f'frames[{frame_index}][{row_index}] column count must be {BOARD_WIDTH}')

        normalized_pixels = []
        for column_index, pixel in enumerate(row):
            if not isinstance(pixel, list) or len(pixel) != 3:
                raise ValueError(f'frames[{frame_index}][{row_index}][{column_index}] must be an RGB triplet')

            rgb = [int(channel) for channel in pixel]
            for channel in rgb:
                if channel < 0 or channel > 255:
                    raise ValueError(
                        f'frames[{frame_index}][{row_index}][{column_index}] contains an out-of-range RGB value'
                    )
            normalized_pixels.append(rgb)
        normalized_rows.append(normalized_pixels)

    return normalized_rows


def _unwrap_frame_payload(frame):
    if isinstance(frame, dict) and 'frame' in frame:
        return frame.get('frame')
    return frame


__all__ = [
    'AudioInputFrame',
    'render_frames_with_node',
]
