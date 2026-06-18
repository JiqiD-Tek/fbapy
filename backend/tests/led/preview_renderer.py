from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from PIL import Image, ImageDraw

from backend.app.cloud.service.led.ledword.core import BOARD_HEIGHT, BOARD_WIDTH


FrameRow = List[List[int]]
FrameGrid = List[FrameRow]
FrameSequence = List[FrameGrid]

_PALETTE = getattr(Image, 'Palette', Image)
_DITHER = getattr(Image, 'Dither', Image)


@dataclass(frozen=True)
class PreviewArtifacts:
    gif_path: Path


def write_preview_artifacts(
    *,
    output_prefix: Path,
    frames: FrameSequence,
    scale: int,
    duration_ms: int,
) -> PreviewArtifacts:
    if not frames:
        raise ValueError('frames must not be empty')

    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    gif_path = output_prefix.with_suffix('.gif')

    images = [render_led_frame_image(frame, scale=scale) for frame in frames]
    images[0].save(
        gif_path,
        save_all=True,
        append_images=images[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
    )
    return PreviewArtifacts(gif_path=gif_path)


def render_led_frame_image(frame: FrameGrid, *, scale: int) -> Image.Image:
    width = BOARD_WIDTH * scale
    height = BOARD_HEIGHT * scale
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, 'RGBA')

    inner_inset = max(1, scale // 7)

    for row_index, row in enumerate(frame):
        for column_index, pixel in enumerate(row):
            red, green, blue = (int(pixel[0]), int(pixel[1]), int(pixel[2]))
            left = column_index * scale
            top = row_index * scale
            right = (column_index + 1) * scale - 1
            bottom = (row_index + 1) * scale - 1

            border_color = _scale_rgb((red, green, blue), 0.58)
            fill_color = (red, green, blue, 255)
            highlight_color = _lift_rgb((red, green, blue), 0.12, minimum_delta=4)

            draw.rectangle((left, top, right, bottom), fill=border_color)

            fill_left = left if column_index == 0 else left + 1
            fill_top = top if row_index == 0 else top + 1
            fill_right = right if column_index == BOARD_WIDTH - 1 else right - 1
            fill_bottom = bottom if row_index == BOARD_HEIGHT - 1 else bottom - 1

            if right - left >= 2 and bottom - top >= 2:
                draw.rectangle(
                    (
                        fill_left,
                        fill_top,
                        fill_right,
                        fill_bottom,
                    ),
                    fill=fill_color,
                )
            else:
                draw.rectangle((left, top, right, bottom), fill=fill_color)

            if right - left > inner_inset + 1 and bottom - top > inner_inset + 1:
                draw.rectangle(
                    (
                        left + 1,
                        top + 1,
                        right - inner_inset,
                        top + inner_inset,
                    ),
                    fill=highlight_color,
                )

    return image.convert('P', palette=_PALETTE.ADAPTIVE, dither=_DITHER.NONE)


def _scale_rgb(color, factor: float):
    red, green, blue = color
    return (
        max(0, min(255, int(round(red * factor)))),
        max(0, min(255, int(round(green * factor)))),
        max(0, min(255, int(round(blue * factor)))),
        255,
    )


def _lift_rgb(color, factor: float, *, minimum_delta: int):
    red, green, blue = color
    return (
        max(0, min(255, int(round(red + max(minimum_delta, red * factor))))),
        max(0, min(255, int(round(green + max(minimum_delta, green * factor))))),
        max(0, min(255, int(round(blue + max(minimum_delta, blue * factor))))),
        255,
    )


__all__ = [
    'FrameGrid',
    'FrameRow',
    'FrameSequence',
    'PreviewArtifacts',
    'render_led_frame_image',
    'write_preview_artifacts',
]
