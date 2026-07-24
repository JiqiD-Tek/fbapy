from __future__ import annotations

from .builder import build_recognition_handoff_reveal_spec


RECOGNITION_HANDOFF_REVEAL_SPEC = build_recognition_handoff_reveal_spec()

__all__ = [
    "RECOGNITION_HANDOFF_REVEAL_SPEC",
]
