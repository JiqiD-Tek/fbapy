from __future__ import annotations

import math
import random
from typing import List, Optional

from backend.app.cloud.service.led.ledword.common import derive_seed
from backend.app.cloud.service.led.ledword.core import BOARD_HEIGHT, BOARD_WIDTH


def build_star_gather_spec_for_points(
    points: List[List[int]],
    *,
    unit_index: int,
    seed: Optional[int],
) -> List[List[float]]:
    rng_seed = derive_seed(seed, 1181 + unit_index * 29) or (unit_index + 1) * 271
    rng = random.Random(rng_seed)
    specs: List[List[float]] = []
    for index, point in enumerate(points):
        target_x = int(point[0])
        target_y = int(point[1])
        if index % 4 == 0:
            start_x = rng.randrange(BOARD_WIDTH)
            start_y = rng.randrange(BOARD_HEIGHT)
        else:
            side = index % 4
            if side == 1:
                start_x = -1
                start_y = rng.randrange(BOARD_HEIGHT)
            elif side == 2:
                start_x = BOARD_WIDTH
                start_y = rng.randrange(BOARD_HEIGHT)
            else:
                start_x = rng.randrange(BOARD_WIDTH)
                start_y = -1 if rng.random() < 0.5 else BOARD_HEIGHT
        sparkle_flag = 1 if (index % 7 == 0 or rng.random() < 0.12) else 0
        twinkle_phase = rng.random() * math.pi * 2.0
        specs.append(
            [
                float(target_x),
                float(target_y),
                float(start_x),
                float(start_y),
                float(sparkle_flag),
                float(twinkle_phase),
            ]
        )
    return specs


__all__ = ["build_star_gather_spec_for_points"]

