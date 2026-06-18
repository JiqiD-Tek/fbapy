from __future__ import annotations

from pathlib import Path


FONT_DIR = Path(__file__).resolve().parent / "font"


def resolve_font_asset(file_name: str) -> Path:
    return FONT_DIR / Path(str(file_name)).name


__all__ = [
    "FONT_DIR",
    "resolve_font_asset",
]
