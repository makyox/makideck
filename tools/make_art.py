"""Draw makideck's pixel art: the logo, the app icon and the menu bar icons.

    uv run python tools/make_art.py

Everything is drawn on small pixel grids and scaled up with nearest-neighbour,
so it stays crisp. The mark is the deck itself: a wide panel on a stand with
the ASCII tunnel on the left and usage bars on the right.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "makideck" / "assets"
DOCS = ROOT / "docs" / "img"

BG = (11, 11, 16, 255)
FRAME = (58, 58, 78, 255)
FRAME_HI = (92, 92, 118, 255)
ORANGE = (217, 119, 87, 255)
ORANGE_HI = (240, 160, 120, 255)
VIOLET = (139, 108, 240, 255)
VIOLET_DIM = (78, 62, 150, 255)
GREEN = (108, 194, 135, 255)
CLEAR = (0, 0, 0, 0)

# 5×7 lowercase, '#' = ink. Ascenders use the top two rows.
GLYPHS = {
    "m": [".....", ".....", "##.#.", "#.#.#", "#.#.#", "#.#.#", "#.#.#"],
    "a": [".....", ".....", ".###.", "....#", ".####", "#...#", ".####"],
    "k": ["#....", "#....", "#..#.", "#.#..", "##...", "#.#..", "#..#."],
    "i": ["..#..", ".....", ".##..", "..#..", "..#..", "..#..", ".###."],
    "d": ["....#", "....#", ".####", "#...#", "#...#", "#...#", ".####"],
    "e": [".....", ".....", ".###.", "#...#", "#####", "#....", ".###."],
    "c": [".....", ".....", ".###.", "#....", "#....", "#....", ".###."],
}


def px(img: Image.Image, x: int, y: int, color) -> None:
    if 0 <= x < img.width and 0 <= y < img.height:
        img.putpixel((x, y), color)


def mark(w: int = 26, h: int = 22) -> Image.Image:
    """The deck on its stand, on a w×h grid."""
    img = Image.new("RGBA", (w, h), CLEAR)
    top, bottom = 2, 14                       # panel rows
    for y in range(top, bottom + 1):
        for x in range(w):
            corner = (x in (0, w - 1)) and (y in (top, bottom))
            if corner:
                continue
            edge = x in (0, w - 1) or y in (top, bottom)
            px(img, x, y, (FRAME_HI if y == top else FRAME) if edge else BG)
    # Tunnel in perspective: two frames and the rays between them.
    def frame(x0: int, x1: int, y0: int, y1: int, color) -> None:
        for x in range(x0, x1 + 1):
            px(img, x, y0, color)
            px(img, x, y1, color)
        for y in range(y0, y1 + 1):
            px(img, x0, y, color)
            px(img, x1, y, color)
    mid_y = (top + bottom) // 2
    for i in (0, 2):                                   # rays, far → near corners
        for x, y in ((1 + i, top + 1 + i), (13 - i, top + 1 + i),
                     (1 + i, bottom - 1 - i), (13 - i, bottom - 1 - i)):
            px(img, x, y, VIOLET_DIM)
    frame(2, 12, top + 2, bottom - 2, ORANGE)
    frame(4, 10, top + 4, bottom - 4, VIOLET)
    for x, y in ((5, top + 5), (9, top + 5), (5, bottom - 5), (9, bottom - 5)):
        px(img, x, y, VIOLET_DIM)
    for x in (6, 7, 8):
        px(img, x, mid_y, VIOLET_DIM)
    px(img, 7, mid_y, ORANGE_HI)
    # Usage bars on the right.
    for i, (height, color) in enumerate(((7, ORANGE), (4, ORANGE), (9, ORANGE_HI), (5, GREEN))):
        x = 15 + i * 2 + (1 if i > 1 else 0)
        for y in range(bottom - 1, bottom - 1 - height, -1):
            px(img, x, y, color)
    # Divider between the two halves.
    for y in range(top + 2, bottom - 1):
        px(img, 14, y, FRAME)
    # Stand.
    mid = w // 2
    for y in (bottom + 1, bottom + 2, bottom + 3):
        px(img, mid - 1, y, FRAME)
        px(img, mid, y, FRAME)
    for x in range(mid - 5, mid + 5):
        px(img, x, bottom + 4, FRAME_HI)
        px(img, x, bottom + 5, FRAME)
    return img


def word(text: str, color, shadow, k: int = 2) -> Image.Image:
    """Text in the 5×7 font, each font pixel k×k grid pixels, with a drop
    shadow one grid pixel down-right."""
    img = Image.new("RGBA", (len(text) * 6 * k + 1, 7 * k + 1), CLEAR)
    for dx, ink in ((1, shadow), (0, color)):
        for i, ch in enumerate(text):
            for y, row in enumerate(GLYPHS[ch]):
                for x, c in enumerate(row):
                    if c == "#":
                        for a in range(k):
                            for b in range(k):
                                px(img, (i * 6 + x) * k + a + dx, y * k + b + dx, ink)
    return img


def scaled(img: Image.Image, k: int) -> Image.Image:
    return img.resize((img.width * k, img.height * k), Image.NEAREST)


def rounded_bg(w: int, h: int, r: int, color) -> Image.Image:
    bg = Image.new("RGBA", (w, h), CLEAR)
    ImageDraw.Draw(bg).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=color)
    return bg


def logo() -> Image.Image:
    """Banner: mark + wordmark on a dark card, pixel grid ×8."""
    m, wm = mark(), word("makideck", ORANGE, VIOLET_DIM)
    grid_w, grid_h = 4 + m.width + 5 + wm.width + 4, m.height + 4
    canvas = Image.new("RGBA", (grid_w, grid_h), CLEAR)
    canvas.alpha_composite(m, (4, 2))
    canvas.alpha_composite(wm, (4 + m.width + 5, 2 + 2))
    k = 8
    out = rounded_bg(grid_w * k, grid_h * k, 6 * k, (14, 14, 20, 255))
    out.alpha_composite(scaled(canvas, k))
    return out


def icon(size: int = 512) -> Image.Image:
    m = mark()
    k = size // 32
    out = rounded_bg(size, size, size // 5, (14, 14, 20, 255))
    art = scaled(m, k)
    out.alpha_composite(art, ((size - art.width) // 2, (size - art.height) // 2 + k))
    return out


def menubar(state: str) -> Image.Image:
    """Template icons for the menu bar: black + alpha, 22×18 pt @2x."""
    ink = (0, 0, 0, 255)
    soft = (0, 0, 0, 120)
    g = Image.new("RGBA", (22, 18), CLEAR)
    for x in range(1, 21):                    # panel outline
        px(g, x, 2, ink)
        px(g, x, 11, ink)
    for y in range(3, 11):
        px(g, 0, y, ink)
        px(g, 21, y, ink)
    for x in range(9, 13):                    # stand
        px(g, x, 15, ink)
    for y in (12, 13, 14):
        px(g, 10, y, ink)
        px(g, 11, y, ink)
    if state == "on":
        for cx, cy, r in ((6, 6.5, 2.6),):
            for y in range(3, 11):
                for x in range(1, 11):
                    if abs(math.hypot(x - cx, (y - cy) * 1.1) - r) < 0.7:
                        px(g, x, y, ink)
        px(g, 6, 6, ink)
        for i, h in enumerate((5, 3, 6)):
            for y in range(10, 10 - h, -1):
                px(g, 13 + i * 3, y, ink)
                px(g, 14 + i * 3, y, ink)
    elif state == "sleep":
        for x, y in ((8, 4), (9, 4), (10, 4), (11, 4), (10, 5), (9, 6), (8, 7), (9, 7), (10, 7), (11, 7)):
            px(g, x, y, ink)
        for x, y in ((13, 7), (14, 7), (15, 7), (14, 8), (13, 9), (14, 9), (15, 9)):
            px(g, x, y, soft)
    else:
        for i in range(8):
            px(g, 7 + i, 3 + i, ink)
            px(g, 14 - i, 3 + i, ink)
    return scaled(g, 2)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    logo().save(DOCS / "logo.png")
    icon(512).save(DOCS / "icon.png")
    icon(64).save(ASSETS / "icon.png")
    for state in ("on", "sleep", "off"):
        menubar(state).save(ASSETS / f"menubar-{state}.png")
    print("wrote", DOCS / "logo.png", DOCS / "icon.png", "and the menu bar icons")


if __name__ == "__main__":
    main()
