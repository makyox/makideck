"""Palette and fonts.

The panel is an IPS strip a few feet from your face, usually in a dim room:
near-black background, one warm accent (Claude orange) and a cool secondary
(violet) for the visualizer. Fonts are the macOS system faces; anything else
falls back to Pillow's bundled one.
"""
from __future__ import annotations

from functools import cache

from PIL import ImageFont

BG = "#0b0b10"
CARD = "#16161f"
LINE = "#262633"
TEXT = "#ebe8e4"
DIM = "#8b8895"
FAINT = "#4c4958"
STALE = "#5b5867"
ACCENT = "#d97757"          # Claude orange
VIOLET = "#8b6cf0"
GOOD = "#6cc287"
WARN = "#e3b04b"
BAD = "#e5675f"
SKY = "#6aa7e8"

# Model shares get these in order, biggest first.
SERIES = (ACCENT, "#7aa0dc", GOOD, WARN, DIM)


def usage_color(pct: float) -> str:
    """Accent while comfortable, amber when close, red at the wall."""
    return BAD if pct >= 95 else WARN if pct >= 80 else ACCENT


_FACES = {
    "sans": ("/System/Library/Fonts/SFNSDisplay.ttf",
             "/System/Library/Fonts/SFNS.ttf",
             "/System/Library/Fonts/Helvetica.ttc"),
    "mono": ("/System/Library/Fonts/SFNSMono.ttf",
             "/System/Library/Fonts/Menlo.ttc"),
}


@cache
def font(face: str, size: int) -> ImageFont.FreeTypeFont:
    for path in _FACES[face]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


def sans(size: int) -> ImageFont.FreeTypeFont:
    return font("sans", size)


def mono(size: int) -> ImageFont.FreeTypeFont:
    return font("mono", size)
