from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from backend.app.cloud.service.resource.providers.led.ledword.core import BOARD_HEIGHT, BOARD_WIDTH
from backend.app.cloud.service.resource.providers.led.ledword.font_paths import FONT_DIR, resolve_font_asset


MaskGrid = List[List[int]]
FrameGrid = List[List[List[int]]]

_RESAMPLING = getattr(Image, "Resampling", Image)
BOX_RESAMPLE = _RESAMPLING.BOX

DEFAULT_FONT_CANDIDATES = (
    resolve_font_asset("MiSans-Heavy.ttf"),
    resolve_font_asset("ZLabsRoundPix_16px_M_CN.ttf"),
)

DEFAULT_ON_COLOR = (255, 170, 72)
DEFAULT_OFF_COLOR = (0, 0, 0)


@dataclass(frozen=True)
class RenderedTextBoard:
    text: str
    mask: MaskGrid
    font_path: Path
    font_size: int
    threshold: int
    lit_pixels: int

    @property
    def rows(self) -> List[str]:
        return mask_to_rows(self.mask)


@dataclass(frozen=True)
class RenderedTextStrip:
    text: str
    mask: MaskGrid
    font_path: Path
    font_size: int
    threshold: int
    lit_pixels: int

    @property
    def width(self) -> int:
        if not self.mask:
            return 0
        return len(self.mask[0])

    @property
    def rows(self) -> List[str]:
        return mask_to_rows(self.mask)


def render_text_board(
    text: str,
    *,
    font_path: Optional[Path] = None,
    supersample: int = 12,
    padding: int = 1,
    threshold: Optional[int] = None,
    anchor_text: Optional[str] = None,
) -> RenderedTextBoard:
    normalized_text = _normalize_text(text)
    resolved_anchor_text = _resolve_anchor_text(normalized_text, anchor_text)
    if supersample <= 0:
        raise ValueError("supersample must be a positive integer")
    if padding < 0:
        raise ValueError("padding must be >= 0")
    if threshold is not None and (threshold < 0 or threshold > 255):
        raise ValueError("threshold must be between 0 and 255")

    resolved_font_path = resolve_font_path(font_path)
    canvas_width = BOARD_WIDTH * supersample
    canvas_height = BOARD_HEIGHT * supersample
    available_width = canvas_width - padding * supersample * 2
    available_height = canvas_height - padding * supersample * 2
    if available_width <= 0 or available_height <= 0:
        raise ValueError("padding leaves no drawable area on the board")

    font_size = _choose_font_size(
        normalized_text,
        font_path=resolved_font_path,
        canvas_width=available_width,
        canvas_height=available_height,
    )
    glyph_image = _render_high_res_text(
        normalized_text,
        font_path=resolved_font_path,
        font_size=font_size,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        anchor_text=resolved_anchor_text,
    )
    downsampled = glyph_image.resize(
        (BOARD_WIDTH, BOARD_HEIGHT),
        resample=BOX_RESAMPLE,
    )
    resolved_threshold = threshold if threshold is not None else _choose_threshold(
        downsampled,
        text_length=len(normalized_text),
    )
    mask = _threshold_image(downsampled, threshold=resolved_threshold)
    lit_pixels = count_lit_pixels(mask)
    if lit_pixels <= 0:
        raise ValueError("text rasterization produced an empty mask")

    return RenderedTextBoard(
        text=normalized_text,
        mask=mask,
        font_path=resolved_font_path,
        font_size=font_size,
        threshold=resolved_threshold,
        lit_pixels=lit_pixels,
    )


def render_text_board_with_font_size(
    text: str,
    *,
    font_size: int,
    font_path: Optional[Path] = None,
    supersample: int = 12,
    padding: int = 1,
    threshold: Optional[int] = None,
    anchor_text: Optional[str] = None,
) -> RenderedTextBoard:
    normalized_text = _normalize_text(text)
    resolved_anchor_text = _resolve_anchor_text(normalized_text, anchor_text)
    if supersample <= 0:
        raise ValueError("supersample must be a positive integer")
    if padding < 0:
        raise ValueError("padding must be >= 0")
    if font_size <= 0:
        raise ValueError("font_size must be a positive integer")
    if threshold is not None and (threshold < 0 or threshold > 255):
        raise ValueError("threshold must be between 0 and 255")

    resolved_font_path = resolve_font_path(font_path)
    canvas_width = BOARD_WIDTH * supersample
    canvas_height = BOARD_HEIGHT * supersample
    available_width = canvas_width - padding * supersample * 2
    available_height = canvas_height - padding * supersample * 2
    if available_width <= 0 or available_height <= 0:
        raise ValueError("padding leaves no drawable area on the board")

    bbox = _measure_text_bbox(
        normalized_text,
        font_path=resolved_font_path,
        font_size=font_size,
    )
    if not _bbox_fits(bbox, width=available_width, height=available_height):
        raise ValueError("requested font_size does not fit on the board")

    glyph_image = _render_high_res_text(
        normalized_text,
        font_path=resolved_font_path,
        font_size=font_size,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        anchor_text=resolved_anchor_text,
    )
    downsampled = glyph_image.resize(
        (BOARD_WIDTH, BOARD_HEIGHT),
        resample=BOX_RESAMPLE,
    )
    resolved_threshold = threshold if threshold is not None else _choose_threshold(
        downsampled,
        text_length=len(normalized_text),
    )
    mask = _threshold_image(downsampled, threshold=resolved_threshold)
    lit_pixels = count_lit_pixels(mask)
    if lit_pixels <= 0:
        raise ValueError("text rasterization produced an empty mask")

    return RenderedTextBoard(
        text=normalized_text,
        mask=mask,
        font_path=resolved_font_path,
        font_size=font_size,
        threshold=resolved_threshold,
        lit_pixels=lit_pixels,
    )


def render_text_strip(
    text: str,
    *,
    font_path: Optional[Path] = None,
    supersample: int = 12,
    padding: int = 1,
    threshold: Optional[int] = None,
) -> RenderedTextStrip:
    normalized_text = _normalize_text(text)
    if supersample <= 0:
        raise ValueError("supersample must be a positive integer")
    if padding < 0:
        raise ValueError("padding must be >= 0")
    if threshold is not None and (threshold < 0 or threshold > 255):
        raise ValueError("threshold must be between 0 and 255")

    resolved_font_path = resolve_font_path(font_path)
    canvas_height = BOARD_HEIGHT * supersample
    available_height = canvas_height - padding * supersample * 2
    if available_height <= 0:
        raise ValueError("padding leaves no drawable area on the board")

    font_size = _choose_font_size_for_height(
        normalized_text,
        font_path=resolved_font_path,
        canvas_height=available_height,
    )
    bbox = _measure_text_bbox(
        normalized_text,
        font_path=resolved_font_path,
        font_size=font_size,
    )
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    canvas_width = max(
        BOARD_WIDTH * supersample,
        text_width + padding * supersample * 2,
    )
    image = Image.new("L", (canvas_width, canvas_height), 0)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(resolved_font_path), size=font_size)
    origin_x = padding * supersample - bbox[0]
    origin_y = (canvas_height - text_height) / 2.0 - bbox[1]
    draw.text((origin_x, origin_y), normalized_text, fill=255, font=font)

    strip_width = max(
        BOARD_WIDTH,
        int(math.ceil(canvas_width / float(supersample))),
    )
    downsampled = image.resize((strip_width, BOARD_HEIGHT), resample=BOX_RESAMPLE)
    resolved_threshold = threshold if threshold is not None else _choose_threshold(
        downsampled,
        text_length=len(normalized_text),
        target_ratio=min(0.22, 0.08 + len(normalized_text) * 0.03),
        minimum_ratio=0.05,
        maximum_ratio=0.26,
    )
    mask = _threshold_image(downsampled, threshold=resolved_threshold)
    lit_pixels = count_lit_pixels(mask)
    if lit_pixels <= 0:
        raise ValueError("text strip rasterization produced an empty mask")

    return RenderedTextStrip(
        text=normalized_text,
        mask=mask,
        font_path=resolved_font_path,
        font_size=font_size,
        threshold=resolved_threshold,
        lit_pixels=lit_pixels,
    )


def resolve_font_path(font_path: Optional[Path] = None) -> Path:
    if font_path is not None:
        resolved = Path(font_path).expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError("font file does not exist: {0}".format(resolved))
        if not _is_relative_to(resolved, FONT_DIR):
            raise FileNotFoundError(
                "font file must be under font directory: {0}".format(FONT_DIR.resolve())
            )
        return resolved

    for candidate in DEFAULT_FONT_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "no usable root font was found; pass --font-path to select one explicitly"
    )


def _is_relative_to(path: Path, base_dir: Path) -> bool:
    try:
        path.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False


def mask_to_rows(mask: MaskGrid) -> List[str]:
    return ["".join("1" if value else "0" for value in row) for row in mask]


def count_lit_pixels(mask: MaskGrid) -> int:
    return sum(sum(row) for row in mask)


def crop_mask_window(
    mask: MaskGrid,
    *,
    left: int,
    width: int = BOARD_WIDTH,
) -> MaskGrid:
    rows: MaskGrid = []
    for row in mask:
        cropped_row: List[int] = []
        for x in range(width):
            source_x = left + x
            if 0 <= source_x < len(row):
                cropped_row.append(row[source_x])
            else:
                cropped_row.append(0)
        rows.append(cropped_row)
    return rows




def _choose_font_size(
    text: str,
    *,
    font_path: Path,
    canvas_width: int,
    canvas_height: int,
) -> int:
    low = 8
    high = max(16, canvas_height * 2)
    best = low
    while low <= high:
        mid = (low + high) // 2
        bbox = _measure_text_bbox(text, font_path=font_path, font_size=mid)
        if _bbox_fits(bbox, width=canvas_width, height=canvas_height):
            best = mid
            low = mid + 1
        else:
            high = mid - 1
    return best


def _choose_font_size_for_height(
    text: str,
    *,
    font_path: Path,
    canvas_height: int,
) -> int:
    low = 8
    high = max(16, canvas_height * 2)
    best = low
    while low <= high:
        mid = (low + high) // 2
        bbox = _measure_text_bbox(text, font_path=font_path, font_size=mid)
        bbox_height = bbox[3] - bbox[1]
        if bbox_height <= canvas_height:
            best = mid
            low = mid + 1
        else:
            high = mid - 1
    return best


def _render_high_res_text(
    text: str,
    *,
    font_path: Path,
    font_size: int,
    canvas_width: int,
    canvas_height: int,
    anchor_text: Optional[str] = None,
) -> Image.Image:
    image = Image.new("L", (canvas_width, canvas_height), 0)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), size=font_size)
    bbox = _measure_text_bbox(text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    origin_x = (canvas_width - text_width) / 2.0 - bbox[0]
    origin_y = (canvas_height - text_height) / 2.0 - bbox[1]
    if anchor_text and anchor_text != text:
        anchored_origin = _resolve_anchor_origin(
            text,
            anchor_text=anchor_text,
            font=font,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
        )
        if anchored_origin is not None:
            origin_x, origin_y = anchored_origin
    draw.text((origin_x, origin_y), text, fill=255, font=font)
    return image


def _resolve_anchor_origin(
    text: str,
    *,
    anchor_text: str,
    font: ImageFont.ImageFont,
    canvas_width: int,
    canvas_height: int,
) -> Optional[Tuple[float, float]]:
    anchor_start = text.find(anchor_text)
    if anchor_start < 0:
        return None

    full_bbox = _measure_text_bbox_at_position(text, position=(0.0, 0.0), font=font)
    full_width = full_bbox[2] - full_bbox[0]
    full_height = full_bbox[3] - full_bbox[1]
    origin_x = (canvas_width - full_width) / 2.0 - full_bbox[0]
    origin_y = (canvas_height - full_height) / 2.0 - full_bbox[1]

    prefix = text[:anchor_start]
    prefix_advance = _measure_text_advance(prefix, font=font)
    anchor_bbox = _measure_text_bbox_at_position(
        anchor_text,
        position=(prefix_advance, 0.0),
        font=font,
    )
    anchor_center_x = origin_x + (anchor_bbox[0] + anchor_bbox[2]) / 2.0
    anchor_center_y = origin_y + (anchor_bbox[1] + anchor_bbox[3]) / 2.0
    origin_x += canvas_width / 2.0 - anchor_center_x
    origin_y += canvas_height / 2.0 - anchor_center_y
    return origin_x, origin_y


def _measure_text_bbox(
    text: str,
    *,
    font_path: Optional[Path] = None,
    font_size: Optional[int] = None,
    font: Optional[ImageFont.ImageFont] = None,
) -> Tuple[int, int, int, int]:
    working_font = font
    if working_font is None:
        if font_path is None or font_size is None:
            raise ValueError("font_path and font_size are required when font is omitted")
        working_font = ImageFont.truetype(str(font_path), size=font_size)

    measurement_image = Image.new("L", (1, 1), 0)
    draw = ImageDraw.Draw(measurement_image)
    textbbox = getattr(draw, "textbbox", None)
    if callable(textbbox):
        return tuple(int(value) for value in textbbox((0, 0), text, font=working_font))

    text_width, text_height = draw.textsize(text, font=working_font)
    return 0, 0, int(text_width), int(text_height)


def _measure_text_bbox_at_position(
    text: str,
    *,
    position: Tuple[float, float],
    font: ImageFont.ImageFont,
) -> Tuple[float, float, float, float]:
    measurement_image = Image.new("L", (1, 1), 0)
    draw = ImageDraw.Draw(measurement_image)
    textbbox = getattr(draw, "textbbox", None)
    if callable(textbbox):
        bbox = textbbox(position, text, font=font)
        return tuple(float(value) for value in bbox)

    text_width, text_height = draw.textsize(text, font=font)
    return (
        float(position[0]),
        float(position[1]),
        float(position[0] + text_width),
        float(position[1] + text_height),
    )


def _measure_text_advance(text: str, *, font: ImageFont.ImageFont) -> float:
    if not text:
        return 0.0
    measurement_image = Image.new("L", (1, 1), 0)
    draw = ImageDraw.Draw(measurement_image)
    textlength = getattr(draw, "textlength", None)
    if callable(textlength):
        return float(textlength(text, font=font))
    bbox = _measure_text_bbox(text, font=font)
    return float(bbox[2] - bbox[0])


def _bbox_fits(
    bbox: Tuple[int, int, int, int],
    *,
    width: int,
    height: int,
) -> bool:
    bbox_width = bbox[2] - bbox[0]
    bbox_height = bbox[3] - bbox[1]
    return bbox_width <= width and bbox_height <= height


def _choose_threshold(
    image: Image.Image,
    *,
    text_length: int,
    target_ratio: Optional[float] = None,
    minimum_ratio: float = 0.08,
    maximum_ratio: float = 0.50,
) -> int:
    pixel_count = image.width * image.height
    resolved_target_ratio = (
        target_ratio
        if target_ratio is not None
        else min(0.38, 0.08 + text_length * 0.075)
    )
    target_pixels = int(pixel_count * resolved_target_ratio)
    minimum_pixels = max(12, int(pixel_count * minimum_ratio))
    maximum_pixels = int(pixel_count * maximum_ratio)
    best_threshold = 96
    best_score = math.inf

    for candidate in (168, 152, 144, 136, 128, 120, 112, 104, 96, 88, 80, 72, 64, 56):
        lit_pixels = count_lit_pixels(_threshold_image(image, threshold=candidate))
        distance = abs(lit_pixels - target_pixels)
        if lit_pixels < minimum_pixels:
            distance += (minimum_pixels - lit_pixels) * 2
        if lit_pixels > maximum_pixels:
            distance += (lit_pixels - maximum_pixels) * 3
        if distance < best_score:
            best_score = distance
            best_threshold = candidate

    return best_threshold


def _normalize_text(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("text must not be empty")
    return normalized


def _resolve_anchor_text(text: str, anchor_text: Optional[str]) -> str:
    if anchor_text is None:
        return text
    normalized_anchor = str(anchor_text or "").strip()
    if not normalized_anchor:
        return text
    if normalized_anchor not in text:
        return text
    return normalized_anchor


def _threshold_image(image: Image.Image, *, threshold: int) -> MaskGrid:
    grayscale = image.convert("L")
    values = list(grayscale.getdata())
    mask: MaskGrid = []
    for row_index in range(grayscale.height):
        offset = row_index * grayscale.width
        mask.append(
            [1 if value >= threshold else 0 for value in values[offset : offset + grayscale.width]]
        )
    return mask


def _json_rows(rows: Sequence[str]) -> str:
    return "[" + ",".join('"{0}"'.format(row) for row in rows) + "]"


def _json_numbers(values: Sequence[int]) -> str:
    return "[" + ",".join(str(int(value)) for value in values) + "]"


__all__ = [
    "MaskGrid",
    "RenderedTextBoard",
    "RenderedTextStrip",
    "count_lit_pixels",
    "crop_mask_window",
    "mask_to_rows",
    "render_text_board",
    "render_text_board_with_font_size",
    "render_text_strip",
    "resolve_font_path",
]

