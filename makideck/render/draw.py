"""Small drawing and formatting helpers shared by tiles and views."""
from __future__ import annotations

from collections.abc import Sequence

from PIL import ImageDraw, ImageFont

from . import theme

Box = tuple[int, int, int, int]


def meter(d: ImageDraw.ImageDraw, box: Box, pct: float, color: str) -> None:
    """A pill-shaped gauge filled to pct (0..100)."""
    x0, y0, x1, y1 = box
    r = (y1 - y0) / 2
    d.rounded_rectangle(box, radius=r, fill=theme.CARD, outline=theme.LINE)
    fill = (x1 - x0) * min(max(pct, 0.0), 100.0) / 100
    if fill <= 0:
        return
    # Below one cap's width a rounded rect degenerates; draw a dot instead.
    d.rounded_rectangle((x0, y0, x0 + max(fill, 2 * r), y1), radius=r, fill=color)


def bars(d: ImageDraw.ImageDraw, box: Box, values: Sequence[float],
         slots: int, color: str = theme.ACCENT) -> None:
    """Column chart with a fixed number of slots (e.g. 24 hours)."""
    x0, y0, x1, y1 = box
    top = max(values, default=0)
    if not top:
        d.line((x0, y1, x1, y1), fill=theme.FAINT)
        return
    step = (x1 - x0) / slots
    for i, v in enumerate(values[:slots]):
        h = max(2.0, (y1 - y0) * v / top)
        left = x0 + i * step
        d.rectangle((left, y1 - h, left + step - 2, y1),
                    fill=color if v else theme.FAINT)


def split_bar(d: ImageDraw.ImageDraw, box: Box,
              parts: Sequence[tuple[float, str]]) -> None:
    """One bar cut into (share, color) parts; shares should sum to ~1."""
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=(y1 - y0) / 2, fill=theme.CARD)
    left = float(x0)
    for share, color in parts:
        right = left + (x1 - x0) * share
        if right - left >= 1:
            d.rectangle((left, y0, right, y1), fill=color)
        left = right


def clip(d: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
         width: float) -> str:
    """text, cut with an ellipsis to fit width pixels."""
    if d.textlength(text, font=font) <= width:
        return text
    lo, hi = 0, len(text)
    while lo < hi:                       # longest prefix that fits with "…"
        mid = (lo + hi + 1) // 2
        if d.textlength(text[:mid] + "…", font=font) <= width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + "…"


def shrink(d: ImageDraw.ImageDraw, text: str, face: str, size: int,
           width: float, smallest: int = 12) -> ImageFont.FreeTypeFont:
    """The biggest font of `face` (from size down) that fits text in width."""
    for s in range(size, smallest - 1, -1):
        f = theme.font(face, s)
        if d.textlength(text, font=f) <= width:
            return f
    return theme.font(face, smallest)


def tokens(n: float) -> str:
    """1234 → 1.2k, 27_100_000 → 27.1M."""
    for unit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if n >= unit:
            return f"{n / unit:.1f}{suffix}"
    return str(int(n))


def until(seconds: float) -> str:
    """Countdown with the two most useful units: 5d 18h, 2h 04m, 7m."""
    s = max(0, int(seconds))
    days, s = divmod(s, 86_400)
    hours, s = divmod(s, 3_600)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {s // 60:02d}m"
    return f"{s // 60}m"


def mmss(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s // 60}:{s % 60:02d}"
