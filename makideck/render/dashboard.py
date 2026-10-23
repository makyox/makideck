"""Compose a frame: the visible tiles side by side over a token-chart footer,
or a full-screen view. Pure functions of the state and the deck layout.
"""
from __future__ import annotations

import time

from PIL import Image, ImageDraw

from .. import deck
from ..state import DeckState
from . import draw, theme, views

SIZE = (1920, 462)          # Trofeo Vision 9.16"
FOOTER = 74


def contexts(img: Image.Image, state: DeckState,
             size: tuple[int, int] | None = None) -> list[tuple[deck.Tile, deck.Ctx]]:
    width, height = size or img.size
    d = ImageDraw.Draw(img)
    return [(t, deck.Ctx(d, img, state, x0, x1, 0, height - FOOTER, deck.settings(t.id)))
            for t, x0, x1 in deck.columns(width)]


def dashboard(state: DeckState, size: tuple[int, int] = SIZE,
              live: bool = True) -> Image.Image:
    """live=False skips the tiles' per-frame layers (the loop paints those
    itself over a cached copy)."""
    img = Image.new("RGB", size, theme.BG)
    placed = contexts(img, state)
    for tile, c in placed:
        try:
            tile.draw(c)
        except Exception as e:                  # one broken tile ≠ a black panel
            c.d.text((c.left, 30), f"{tile.id}: {e}"[:60], font=theme.mono(14), fill=theme.BAD)
    if live:
        paint(img, state, placed)
    d = ImageDraw.Draw(img)
    width, height = size
    for _, c in placed[1:]:
        d.line((c.x0, 24, c.x0, height - FOOTER - 12), fill=theme.LINE)
    d.line((28, height - FOOTER, width - 28, height - FOOTER), fill=theme.LINE)
    d.text((28, height - FOOTER + 12), "TOKENS TODAY", font=theme.sans(15), fill=theme.FAINT)
    draw.bars(d, (178, height - FOOTER + 14, width - 28, height - 16), state.work.hourly, 24)
    return img


def paint(img: Image.Image, state: DeckState, placed=None, now: float | None = None) -> None:
    now = time.time() if now is None else now
    for tile, c in placed or contexts(img, state):
        if tile.paint:
            tile.paint(c, now)


def animated(state: DeckState) -> bool:
    return any(t.animated and t.animated(state)
               for t, _, _ in deck.columns(SIZE[0]))


def frame(state: DeckState, size: tuple[int, int] = SIZE, view: str | None = None) -> Image.Image:
    if view in views.VIEWS:
        return views.render(view, state, size)
    return dashboard(state, size)


def tap_zones(state: DeckState, size: tuple[int, int], view: str | None) -> list[dict]:
    """[{action, tile, box}] for the browser mirror."""
    if view in views.VIEWS:
        cx, cy = views.close_center(size[0])
        r = views.CLOSE_R * 2
        return [{"action": "close", "tile": None, "box": [cx - r, cy - r, cx + r, cy + r]}]
    out = []
    # Tap boxes are geometry only, so a 1×1 stand-in canvas will do.
    for tile, c in contexts(Image.new("RGB", (1, 1)), state, size):
        if tile.taps:
            for action, box in tile.taps(c).items():
                out.append({"action": action, "tile": tile.id, "box": list(box)})
    return out


def hit(state: DeckState, size: tuple[int, int], view: str | None,
        x: int, y: int) -> dict | None:
    for zone in tap_zones(state, size, view):
        x0, y0, x1, y1 = zone["box"]
        if x0 <= x < x1 and y0 <= y < y1:
            return zone
    return None
