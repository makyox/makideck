"""ASCII music visualizer for the Spotify window: a flight through a tunnel
(or a warp starfield) drawn as characters, pulsing with the music.

Levels come from `audio.Analyzer` when a loopback device is listening;
otherwise a synthetic beat derived from the track position keeps it moving.
Animation state (distance travelled, spin, stars) lives on the module-level
VIZ so consecutive frames continue the same flight; motion is time-based, so
the frame rate only changes smoothness, not speed.

Characters are drawn one text call per (row, colour bucket) — monospace keeps
the columns aligned — which keeps a frame at a few milliseconds.
"""
from __future__ import annotations

import colorsys
import math
import random
import threading
import time
from functools import lru_cache

from PIL import Image, ImageDraw

from ..state import Music
from . import theme

RAMP = " .,:;-~=+*x#%@"
SCENES = ("tunnel", "stars")
_HUE_FAR, _HUE_SPAN = 262.0, 115.0     # violet in the distance → Claude orange
_HUE_STEPS, _LUM_STEPS = 10, 8


@lru_cache(maxsize=256)
def _color(hue_i: int, lum_i: int) -> tuple[int, int, int]:
    hue = (_HUE_FAR + (hue_i + 0.5) * (_HUE_SPAN + 25) / _HUE_STEPS) % 360
    light = 0.18 + 0.62 * (lum_i + 1) / _LUM_STEPS
    r, g, b = colorsys.hls_to_rgb(hue / 360, light, 0.7)
    return int(r * 255), int(g * 255), int(b * 255)


def _bpm(track_id: str) -> int:
    """Stand-in tempo per track (stable, 112–135) when we can't hear it."""
    h = 0
    for c in track_id:
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    return 112 + h % 24


class AsciiViz:
    def __init__(self, font_size: int = 12) -> None:
        self.font = theme.mono(font_size)
        self.cw = self.font.getlength("M")
        self.ch = font_size + 1
        self.audio = None                  # audio.Analyzer, set by the app
        self.scene = 0
        self._lock = threading.Lock()
        self._last: float | None = None
        self._travel = self._rot = 0.0
        self._stars = [[random.uniform(-1, 1), random.uniform(-1, 1),
                        random.random()] for _ in range(220)]

    def next_scene(self) -> None:
        with self._lock:
            self.scene = (self.scene + 1) % len(SCENES)

    def animated(self, music: Music) -> bool:
        """Worth a high frame rate: something is playing (or audible)."""
        return music.state == "playing" or bool(self.audio and self.audio.active)

    def animated_state(self, state) -> bool:
        return self.animated(state.music)

    def levels(self, music: Music, now: float) -> tuple[float, float, float, float]:
        if self.audio and self.audio.active:
            return self.audio.levels()
        if music.state != "playing":
            return 0.0, 0.0, 0.0, 0.0
        beats = music.position(now) * _bpm(music.track_id) / 60
        ph = beats % 1
        return (math.exp(-ph * 4),
                0.45 + 0.35 * math.sin(beats * math.pi / 8),
                0.3 + 0.4 * max(0.0, math.sin(beats * 2 * math.pi + 1.3)) * random.random(),
                math.exp(-ph * 7))

    def draw(self, img: Image.Image, box: tuple[int, int, int, int],
             music: Music, now: float | None = None) -> None:
        now = time.time() if now is None else now
        dt = 0.0 if self._last is None else min(0.2, max(0.0, now - self._last))
        self._last = now
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        cols, rows = int(w // self.cw), int(h // self.ch)
        lv = self.levels(music, now)
        go = 1.0 if self.animated(music) else 0.12
        cells = (self._tunnel if self.scene == 0 else self._stars_scene)(
            cols, rows, now, dt, lv, go)

        dim = 1.0 if go == 1.0 else 0.55
        tile = Image.new("RGB", (w, h), theme.BG)
        d = ImageDraw.Draw(tile)
        ox, oy = (w - cols * self.cw) / 2, (h - rows * self.ch) / 2
        for j in range(rows):
            buckets: dict[tuple[int, int], list[str]] = {}
            for i in range(cols):
                ch, lum, hue = cells[j * cols + i]
                lum *= dim
                if lum < 0.04:
                    continue
                if ch is None:
                    ch = RAMP[min(len(RAMP) - 1, int(lum * len(RAMP)))]
                    if ch == " ":
                        continue
                key = (min(_HUE_STEPS - 1, max(0, int(hue * _HUE_STEPS))),
                       min(_LUM_STEPS - 1, int(lum * _LUM_STEPS)))
                buckets.setdefault(key, [" "] * cols)[i] = ch
            for key, chars in buckets.items():
                d.text((ox, oy + j * self.ch), "".join(chars).rstrip(),
                       font=self.font, fill=_color(*key))
        img.paste(tile, (x0, y0))

    # Each scene returns cols*rows cells of (char or None for ramp, lum 0..1,
    # hue 0..1 where 0 = far/violet and 1 = near/orange).

    def _tunnel(self, cols, rows, t, dt, lv, go):
        bass, mid, high, beat = lv
        self._travel += dt * (0.5 + 2.6 * bass + 1.5 * beat) * go
        self._rot += dt * (0.05 + 0.35 * mid) * go
        cw, ch = self.cw, self.ch
        w, h = cols * cw, rows * ch
        cx = w / 2 + math.sin(t * 0.55) * w * 0.14 * (0.3 + mid)
        cy = h / 2 + math.cos(t * 0.41) * h * 0.14 * (0.3 + mid)
        reach = min(w, h) * 0.62
        twist = 0.08 + 0.12 * mid
        tau = 2 * math.pi
        out = []
        for j in range(rows):
            py = (j + 0.5) * ch - cy
            for i in range(cols):
                px = (i + 0.5) * cw - cx
                r = math.hypot(px, py) + 1e-3
                z = 130 / r
                v = z + self._travel
                u = math.atan2(py, px) / tau + self._rot + z * twist
                ring = max(0.0, math.cos(v * tau)) ** 3
                stripe = max(0.0, math.cos(u * 8 * tau)) ** 6
                kick = beat if int(v) % 3 == 0 else 0.0  # every 3rd ring flashes
                near = min(1.0, r / reach)
                b = (0.85 * ring * (0.35 + 0.65 * stripe) + 0.25 * stripe * high
                     + 0.6 * kick * ring) * near ** 0.6
                out.append((None, min(1.0, 1.4 * b), near + 0.17 * beat))
        return out

    def _stars_scene(self, cols, rows, t, dt, lv, go):
        bass, mid, high, beat = lv
        out = [(None, 0.0, 0.0)] * (cols * rows)
        speed = (0.12 + 0.9 * bass + 0.8 * beat) * go
        cx = cols / 2 + math.sin(t * 0.4) * cols * 0.08
        cy = rows / 2 + math.cos(t * 0.33) * rows * 0.1
        spin = dt * (0.05 + 0.3 * mid) * go
        cs, sn = math.cos(spin), math.sin(spin)
        aspect = self.cw / self.ch * 2
        for s in self._stars:
            s[0], s[1] = s[0] * cs - s[1] * sn, s[0] * sn + s[1] * cs
            z0 = s[2]
            s[2] -= dt * speed
            if s[2] <= 0.02:
                s[:] = [random.uniform(-1, 1), random.uniform(-1, 1), 1.0]
                continue
            steps = 1 + min(8, int((z0 - s[2]) * 60))     # streak back to z0
            for n in range(steps + 1):
                z = s[2] + (z0 - s[2]) * n / steps
                col = round(cx + s[0] / z * cols * 0.25)
                row = round(cy + s[1] / z * rows * 0.25 * aspect)
                if not (0 <= col < cols and 0 <= row < rows):
                    continue
                k = row * cols + col
                b = (1 - z) * (1.0 if n == 0 else 0.55)
                if b <= out[k][1]:
                    continue
                if n == 0:
                    c = "@" if z < 0.25 else "*" if z < 0.5 else "+" if z < 0.75 else "."
                else:
                    dx, dy = s[0], s[1] * 2
                    c = ("-" if abs(dx) > 2 * abs(dy) else "|" if abs(dy) > 2 * abs(dx)
                         else "\\" if dx * dy > 0 else "/")
                out[k] = (c, min(1.0, b * 1.3 + 0.25 * beat), 1 - z + 0.15 * beat)
        return out


VIZ = AsciiViz()
