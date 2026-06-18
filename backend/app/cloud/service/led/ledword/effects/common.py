from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, List, Optional

from backend.app.cloud.service.led.ledword.common import derive_seed, resolve_local_palette
from backend.app.cloud.service.led.ledword.core import BOARD_HEIGHT, BOARD_WIDTH
from backend.app.cloud.service.led.ledword.styles import BackgroundStylePreset
from backend.app.cloud.service.led.ledword.text_board import render_text_board


def extract_visible_units(text: str) -> List[str]:
    return [char for char in str(text or "") if not char.isspace()]


def resolve_local_four_way_palette(
    background_style: BackgroundStylePreset,
) -> Dict[str, List[int]]:
    return resolve_local_palette(background_style.name)


def build_ordered_pixel_points_for_unit(
    unit: str,
    *,
    font_path: Path,
    order_mode: str,
    unit_index: int,
    seed: Optional[int],
) -> List[List[int]]:
    rendered_unit = render_text_board(
        unit,
        font_path=font_path,
    )
    lit_points: List[List[int]] = []
    center_x = (BOARD_WIDTH - 1) / 2.0
    center_y = (BOARD_HEIGHT - 1) / 2.0
    rng_seed = derive_seed(seed, 941 + unit_index * 17) or (unit_index + 1) * 193
    rng = random.Random(rng_seed)
    for y, row in enumerate(rendered_unit.mask):
        for x, value in enumerate(row):
            if not value:
                continue
            lit_points.append([x, y])

    def sort_key(point: List[int]) -> tuple[float, float, float]:
        x = point[0]
        y = point[1]
        if order_mode == "left_to_right":
            return (float(x), float(y), 0.0)
        if order_mode == "bottom_to_top":
            return (float(-y), float(x), 0.0)
        if order_mode == "pseudo_random":
            return (rng.random(), float(y), float(x))
        distance = (x - center_x) * (x - center_x) + (y - center_y) * (y - center_y)
        return (float(distance), float(y), float(x))

    lit_points.sort(key=sort_key)
    return lit_points


__all__ = [
    "build_ordered_pixel_points_for_unit",
    "extract_visible_units",
    "resolve_local_four_way_palette",
]
