from __future__ import annotations

import asyncio
import json
import re
import sys

from datetime import datetime
from pathlib import Path
from typing import Any


if __package__ in {None, ''}:
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from backend.app.cloud.service.resource.providers.led.selector import (
    recommended_design_candidates_for_text,
    resolve_generation_selection,
)
from backend.app.cloud.service.resource.providers.led import led_service
from backend.tests.led.preview_renderer import write_preview_artifacts
from backend.tests.led.preview_runtime import render_frames_with_node


TEST_TEXT = '人人上山人人下山'
TEST_TEXT = '美好'
TEST_STYLE_SEED: int | None = None
TEST_BACKGROUND_STYLE: str | None = None
TEST_OUTPUT_DIR = Path(__file__).resolve().parent / 'output'
TEST_RENDER_SCALE = 18
TEST_FRAME_INTERVAL_MS = 30
KEEP_PROMPT_TXT = True
GENERATE_AUTO_RESULT = True


async def generate_debug_bundle() -> Path:
    output_dir = prepare_output_dir(base_dir=TEST_OUTPUT_DIR, text=TEST_TEXT)
    summary: list[dict[str, Any]] = []

    if GENERATE_AUTO_RESULT:
        auto_selection = resolve_generation_selection(
            text=TEST_TEXT,
            design_type=None,
            font_style=None,
            background_style=TEST_BACKGROUND_STYLE,
            style_seed=TEST_STYLE_SEED,
        )
        auto_result = await led_service.generate_animation(
            text=TEST_TEXT,
            design_type=auto_selection.design_type,
            font_style=auto_selection.font_style,
            background_style=auto_selection.background_style,
            style_seed=TEST_STYLE_SEED,
        )
        auto_dir = output_dir / '_auto'
        auto_dir.mkdir(parents=True, exist_ok=True)
        summary.append(await write_debug_bundle(result=auto_result, output_dir=auto_dir))

    for candidate in recommended_design_candidates_for_text(TEST_TEXT):
        result = await led_service.generate_animation(
            text=TEST_TEXT,
            design_type=candidate.design_type,
            font_style=candidate.font_style,
            background_style=TEST_BACKGROUND_STYLE,
            style_seed=TEST_STYLE_SEED,
        )
        design_dir = output_dir / sanitize_text_for_path(candidate.design_type)
        design_dir.mkdir(parents=True, exist_ok=True)
        summary.append(await write_debug_bundle(result=result, output_dir=design_dir))

    (output_dir / 'summary.json').write_text(
        json.dumps(
            {
                'generated_at': datetime.now().isoformat(timespec='seconds'),
                'text': TEST_TEXT,
                'style_seed': TEST_STYLE_SEED,
                'background_style': TEST_BACKGROUND_STYLE,
                'recommended_designs': [
                    {
                        'design_type': candidate.design_type,
                        'font_style': candidate.font_style,
                    }
                    for candidate in recommended_design_candidates_for_text(TEST_TEXT)
                ],
                'items': summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    return output_dir


async def write_debug_bundle(
    *,
    result: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    output_prefix = output_dir / 'animation'
    js_path = output_prefix.with_suffix('.js')
    metadata_path = output_dir / 'metadata.json'
    prompt_path = output_prefix.with_suffix('.prompt.txt')

    js_path.write_text(result['function_code'].rstrip() + '\n', encoding='utf-8')
    metadata_path.write_text(
        json.dumps(_build_metadata(result), ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    if KEEP_PROMPT_TXT:
        prompt_path.write_text(str(result['prompt']).rstrip() + '\n', encoding='utf-8')

    frame_count = max(1, int(result['loop_length_frames']))
    frames = render_frames_with_node(
        audio_frames=[{} for _ in range(frame_count)],
        function_code=result['function_code'],
    )
    artifacts = write_preview_artifacts(
        output_prefix=output_prefix,
        frames=frames,
        scale=TEST_RENDER_SCALE,
        duration_ms=TEST_FRAME_INTERVAL_MS,
    )

    return {
        'design_type': result['design_type'],
        'design_display_name': result['design_display_name'],
        'text_effect_name': result['text_effect_name'],
        'font_style': result['font_style'],
        'background_style': result['background_style'],
        'loop_length_frames': result['loop_length_frames'],
        'gif_path': str(artifacts.gif_path),
        'js_path': str(js_path),
        'output_dir': str(output_dir),
    }


def prepare_output_dir(*, base_dir: Path, text: str) -> Path:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    text_slug = sanitize_text_for_path(text)
    output_dir = base_dir / f'{timestamp}_{text_slug}'
    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def sanitize_text_for_path(text: str) -> str:
    normalized = re.sub(r'\s+', '_', str(text or '').strip())
    normalized = re.sub(r'[<>:"/\\\\|?*\x00-\x1f]+', '_', normalized)
    normalized = re.sub(r'_+', '_', normalized).strip('._ ')
    if not normalized:
        return 'led_debug'
    return normalized[:32]


def _build_metadata(result: dict[str, Any]) -> dict[str, Any]:
    return {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'text': TEST_TEXT,
        'style_seed': TEST_STYLE_SEED,
        'background_style': TEST_BACKGROUND_STYLE,
        'render_scale': TEST_RENDER_SCALE,
        'frame_interval_ms': TEST_FRAME_INTERVAL_MS,
        'result': result,
    }


def main() -> int:
    try:
        output_dir = asyncio.run(generate_debug_bundle())
    except Exception as exc:
        print(f'生成失败: {exc}', file=sys.stderr)
        return 1

    print(f'输出目录: {output_dir}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
