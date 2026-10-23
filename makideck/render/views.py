"""Full-screen views a tile can open with a tap ("open:<name>").

A view draws the whole panel and gets a close button top-right; the UI
closes it on a tap there, on Esc in the browser, or after a minute.
"""
from __future__ import annotations

from collections.abc import Callable

from PIL import Image, ImageDraw

from ..state import DeckState
from . import theme

CLOSE_R = 30
_PAD = 28
VIEWS: dict[str, Callable[[DeckState, ImageDraw.ImageDraw, tuple[int, int]], None]] = {}


def register(name: str, fn: Callable[[DeckState, ImageDraw.ImageDraw, tuple[int, int]], None]) -> None:
    VIEWS[name] = fn


def close_center(width: int) -> tuple[int, int]:
    return width - _PAD - CLOSE_R, 22 + CLOSE_R


def render(name: str, state: DeckState, size: tuple[int, int]) -> Image.Image:
    img = Image.new("RGB", size, theme.BG)
    d = ImageDraw.Draw(img)
    VIEWS[name](state, d, size)
    cx, cy = close_center(size[0])
    d.ellipse((cx - CLOSE_R, cy - CLOSE_R, cx + CLOSE_R, cy + CLOSE_R),
              fill=theme.CARD, outline=theme.LINE, width=2)
    for sx in (-1, 1):
        d.line((cx - 11, cy - 11 * sx, cx + 11, cy + 11 * sx), fill=theme.TEXT, width=4)
    return img
