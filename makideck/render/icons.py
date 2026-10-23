"""Weather icons drawn from primitives (PIL can't render color emoji).

`weather_icon` maps a WMO weather code to one of a handful of glyphs; `s` is
the icon's nominal width in pixels, centred on (cx, cy).
"""
from __future__ import annotations

from PIL import ImageDraw

SUN = "#f2c14e"
CLOUD = "#b8b6c2"
DARK_CLOUD = "#7d7a8a"
RAIN = "#6aa7e8"
SNOW = "#e8eef7"
BOLT = "#f2c14e"

_LABELS = {
    "clear": "clear", "partly": "partly cloudy", "cloudy": "cloudy",
    "fog": "fog", "drizzle": "drizzle", "rain": "rain", "snow": "snow",
    "storm": "storm",
}


def kind(code: int) -> str:
    if code == 0:
        return "clear"
    if code in (1, 2):
        return "partly"
    if code == 3:
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 57:
        return "drizzle"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow"
    if code >= 95:
        return "storm"
    return "rain"


def label(code: int) -> str:
    return _LABELS[kind(code)]


def _sun(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float) -> None:
    import math
    for i in range(8):
        a = i * math.pi / 4
        d.line((cx + math.cos(a) * r * 1.35, cy + math.sin(a) * r * 1.35,
                cx + math.cos(a) * r * 1.8, cy + math.sin(a) * r * 1.8),
               fill=SUN, width=max(2, int(r / 5)))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=SUN)


def _cloud(d: ImageDraw.ImageDraw, cx: float, cy: float, s: float,
           color: str) -> None:
    w, h = s * 0.9, s * 0.32
    d.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                        radius=h / 2, fill=color)
    r1, r2 = s * 0.2, s * 0.26
    d.ellipse((cx - w / 4 - r1, cy - h / 2 - r1 * 0.9,
               cx - w / 4 + r1, cy - h / 2 + r1 * 1.1), fill=color)
    d.ellipse((cx + w / 10 - r2, cy - h / 2 - r2 * 1.1,
               cx + w / 10 + r2, cy - h / 2 + r2 * 0.9), fill=color)


def weather_icon(d: ImageDraw.ImageDraw, cx: float, cy: float, s: float,
                 code: int) -> None:
    k = kind(code)
    if k == "clear":
        _sun(d, cx, cy, s * 0.24)
        return
    if k == "partly":
        _sun(d, cx - s * 0.16, cy - s * 0.14, s * 0.18)
        _cloud(d, cx + s * 0.06, cy + s * 0.1, s * 0.8, CLOUD)
        return
    if k == "fog":
        for i in range(4):
            y = cy - s * 0.24 + i * s * 0.16
            off = s * 0.08 * (i % 2)
            d.line((cx - s * 0.4 + off, y, cx + s * 0.4 - off, y),
                   fill=CLOUD, width=max(2, int(s / 14)))
        return

    dark = k in ("rain", "storm", "snow")
    _cloud(d, cx, cy - s * 0.1, s, DARK_CLOUD if dark else CLOUD)
    base = cy + s * 0.12
    if k in ("rain", "drizzle"):
        n = 3 if k == "rain" else 2
        for i in range(n):
            x = cx - s * 0.2 + i * s * 0.4 / max(1, n - 1)
            d.line((x, base, x - s * 0.07, base + s * 0.22),
                   fill=RAIN, width=max(2, int(s / 16)))
    elif k == "snow":
        for i in range(3):
            x = cx - s * 0.22 + i * s * 0.22
            y = base + s * 0.12 + (i % 2) * s * 0.08
            r = s * 0.045
            d.ellipse((x - r, y - r, x + r, y + r), fill=SNOW)
    elif k == "storm":
        x, y = cx, base - s * 0.02
        d.polygon([(x + s * 0.06, y), (x - s * 0.1, y + s * 0.18),
                   (x, y + s * 0.18), (x - s * 0.08, y + s * 0.36),
                   (x + s * 0.14, y + s * 0.12), (x + s * 0.03, y + s * 0.12)],
                  fill=BOLT)

