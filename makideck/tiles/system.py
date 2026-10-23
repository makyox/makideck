"""SYS//CORE — the Mac's load, drawn like a terminal from the future.

CPU total with a segmented ring (load average inside), one segmented bar per
core (efficiency and performance cores marked), the last minute of CPU as an
ASCII sparkline, memory split into wired / apps / cache / free, and a status
line with network, uptime, processes and disk.

Numbers come from psutil, sampled every second by a source that starts when
the tile first goes on the panel.
"""
from __future__ import annotations

import math
import os
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field

import psutil

from ..deck import Ctx, Tile, register
from ..render import draw, theme
from ..store import Source

CYAN = "#4fd8e8"
CYAN_DIM = "#1f5a63"
SPARKS = " ▁▂▃▄▅▆▇█"
HISTORY = 90                    # seconds kept for the sparkline


def _sysctl(name: str) -> str:
    try:
        return subprocess.run(["/usr/sbin/sysctl", "-n", name], capture_output=True, text=True,
                              timeout=2).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _chip() -> tuple[str, list[str]]:
    """('M1 MAX', ['E', 'E', 'P', ...]) — Apple Silicon numbers its
    efficiency cores first."""
    name = _sysctl("machdep.cpu.brand_string").removeprefix("Apple ").upper() or "MAC"
    cores = psutil.cpu_count() or 1
    try:
        e = int(_sysctl("hw.perflevel1.logicalcpu") or 0)
    except ValueError:
        e = 0
    return name, ["E"] * e + ["P"] * (cores - e)


@dataclass
class Sample:
    at: float = 0.0
    cpu: float = 0.0
    cores: list[float] = field(default_factory=list)
    load: tuple[float, float, float] = (0.0, 0.0, 0.0)
    mem_total: int = 0
    mem_wired: int = 0
    mem_apps: int = 0
    mem_cache: int = 0
    mem_free: int = 0
    swap_used: int = 0
    net_up: float = 0.0          # bytes/s
    net_down: float = 0.0
    procs: int = 0
    disk_pct: float = 0.0
    uptime_s: float = 0.0


class _Meter:
    """Latest sample + CPU history, shared between the source and draw."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last = Sample()
        self.history: deque[float] = deque(maxlen=HISTORY)
        self._net = None
        self._chip: tuple[str, list[str]] | None = None
        psutil.cpu_percent(percpu=True)          # prime: the first call has no baseline

    @property
    def chip(self) -> str:
        return self._identify()[0]

    @property
    def kinds(self) -> list[str]:
        return self._identify()[1]

    def _identify(self) -> tuple[str, list[str]]:
        if self._chip is None:
            self._chip = _chip()
        return self._chip

    def sample(self) -> Sample:
        now = time.time()
        cores = psutil.cpu_percent(percpu=True)
        vm, sw, net = psutil.virtual_memory(), psutil.swap_memory(), psutil.net_io_counters()
        up = down = 0.0
        if self._net:
            t0, sent, recv = self._net
            dt = max(now - t0, 1e-3)
            up, down = (net.bytes_sent - sent) / dt, (net.bytes_recv - recv) / dt
        self._net = (now, net.bytes_sent, net.bytes_recv)
        wired = getattr(vm, "wired", 0)
        apps = getattr(vm, "active", vm.used)
        cache = getattr(vm, "inactive", 0)
        s = Sample(at=now, cpu=sum(cores) / len(cores) if cores else 0.0, cores=cores,
                   load=os.getloadavg(), mem_total=vm.total, mem_wired=wired, mem_apps=apps,
                   mem_cache=cache, mem_free=max(0, vm.total - wired - apps - cache),
                   swap_used=sw.used, net_up=up, net_down=down, procs=len(psutil.pids()),
                   disk_pct=psutil.disk_usage("/").percent, uptime_s=now - psutil.boot_time())
        with self.lock:
            self.last = s
            self.history.append(s.cpu)
        return s

    def read(self) -> tuple[Sample, list[float]]:
        with self.lock:
            last, hist = self.last, list(self.history)
        if not last.at:                          # no source running (preview): sample once
            time.sleep(0.2)
            return self.sample(), [self.last.cpu]
        return last, hist


METER = _Meter()


class SystemLoad(Source):
    every = 1.0

    def poll(self) -> None:
        METER.sample()


# ── drawing ─────────────────────────────────────────────────────────────

def heat(pct: float) -> str:
    """Cool cyan while idle, accent when busy, red when pinned."""
    return theme.BAD if pct >= 90 else theme.ACCENT if pct >= 60 else CYAN


def gib(n: float) -> str:
    return f"{n / 2**30:.1f}"


def rate(n: float) -> str:
    for unit, div in (("G", 1e9), ("M", 1e6), ("k", 1e3)):
        if n >= div:
            return f"{n / div:.1f}{unit}"
    return f"{n:.0f}"


def ring(d, cx: float, cy: float, r: float, pct: float, segments: int = 32) -> None:
    lit = round(segments * min(pct, 100) / 100)
    span = 300 / segments                          # a 300° dial, open at the bottom
    for i in range(segments):
        start = 120 + i * span
        color = heat(100 * (i + 1) / segments) if i < lit else theme.LINE
        d.arc((cx - r, cy - r, cx + r, cy + r), start, start + span - 3, fill=color, width=7)
    for a in (120, 420):                           # end ticks
        rad = math.radians(a)
        d.line((cx + (r + 3) * math.cos(rad), cy + (r + 3) * math.sin(rad),
                cx + (r + 9) * math.cos(rad), cy + (r + 9) * math.sin(rad)), fill=theme.FAINT, width=2)


def cells(d, x0: float, y: float, x1: float, h: float, parts: list[tuple[float, str]],
          n: int = 26, gap: float = 3) -> None:
    """A bar of n separate cells, coloured left to right by (share, colour)."""
    w = (x1 - x0 - gap * (n - 1)) / n
    edges, acc = [], 0.0
    for share, color in parts:
        acc += share
        edges.append((acc, color))
    for i in range(n):
        mid = (i + 0.5) / n
        color = next((c for e, c in edges if mid <= e), theme.LINE)
        left = x0 + i * (w + gap)
        d.rectangle((left, y, left + w, y + h), fill=color)


def render(c: Ctx) -> None:
    d = c.d
    s, hist = METER.read()
    left, right = c.left, c.right
    small, tiny = theme.mono(14), theme.mono(12)

    # Header: chip name + a blinking LIVE.
    for i, shade in enumerate((CYAN, "#38a3ae", "#267079")):    # ▓▒░, drawn: fonts lack them
        d.rectangle((left + i * 9, 26, left + i * 9 + 6, 40), fill=shade)
    d.text((left + 34, 22), f"SYS::{METER.chip}", font=theme.mono(17), fill=CYAN)
    blink = c.state.now.second % 2 == 0
    d.text((right, 25), "● LIVE", font=tiny, fill=theme.GOOD if blink else theme.FAINT, anchor="ra")
    y = 50
    d.line((left, y, right, y), fill=CYAN_DIM)
    for x in range(int(left), int(right) + 1, 24):
        d.line((x, y, x, y + 4), fill=CYAN_DIM)

    # CPU: big number on the left, the dial on the right.
    d.text((left, 62), "CPU//TOTAL", font=small, fill=theme.FAINT)
    d.text((left - 2, 78), f"{s.cpu:3.0f}%", font=theme.mono(46), fill=heat(s.cpu))
    p = sum(1 for k in METER.kinds if k == "P")
    e = len(METER.kinds) - p
    d.text((left, 132), f"{p}P + {e}E CORES" if e else f"{p} CORES", font=tiny, fill=theme.FAINT)
    cx, cy, r = right - 46, 104, 42
    ring(d, cx, cy, r, s.cpu)
    d.text((cx, cy - 13), "LOAD", font=tiny, fill=theme.FAINT, anchor="mm")
    d.text((cx, cy + 5), f"{s.load[0]:.1f}", font=theme.mono(19), fill=theme.TEXT, anchor="mm")
    d.text((cx, cy + 26), f"{s.load[1]:.0f}·{s.load[2]:.0f}", font=tiny, fill=theme.FAINT, anchor="mm")

    # Per-core towers.
    top, bottom, segs = 156, 206, 9
    n = max(len(s.cores), 1)
    gap = 4
    col_w = (right - left - gap * (n - 1)) / n
    seg_h = (bottom - top) / segs
    for i, pct in enumerate(s.cores):
        x = left + i * (col_w + gap)
        lit = round(segs * pct / 100)
        kind = METER.kinds[i] if i < len(METER.kinds) else "P"
        for k in range(segs):
            y1 = bottom - k * seg_h
            on = k < lit
            color = heat(100 * (k + 1) / segs) if on else (theme.CARD if kind == "P" else "#151020")
            d.rectangle((x, y1 - seg_h + 2, x + col_w, y1), fill=color)
        d.text((x + col_w / 2, bottom + 4), kind, font=theme.mono(11),
               fill=theme.VIOLET if kind == "E" else CYAN_DIM, anchor="ma")

    # Sparkline of the last minute and a half, as characters.
    y = 228
    font = theme.mono(16)
    width = int((right - left - 34) // d.textlength("█", font=font))
    values = hist[-width:]
    line = "".join(SPARKS[min(len(SPARKS) - 1, round(v / 100 * (len(SPARKS) - 1)))] for v in values)
    d.text((left, y), line.rjust(width, SPARKS[0]), font=font, fill=CYAN)
    d.text((right, y + 2), f"{HISTORY}s", font=tiny, fill=theme.FAINT, anchor="ra")

    # Memory.
    y = 258
    total = s.mem_total or 1
    used = s.mem_wired + s.mem_apps
    d.text((left, y), "MEM//MAP", font=small, fill=theme.FAINT)
    d.text((right, y - 3), f"{gib(used)} / {gib(total)} GB", font=theme.mono(18), fill=theme.TEXT, anchor="ra")
    cells(d, left, y + 26, right, 12, [(s.mem_wired / total, theme.ACCENT), (s.mem_apps / total, theme.VIOLET),
                                       (s.mem_cache / total, "#3a2f66")])
    legend = f"wired {gib(s.mem_wired)}  apps {gib(s.mem_apps)}  cache {gib(s.mem_cache)}"
    d.text((left, y + 46), draw.clip(d, legend, tiny, right - left), font=tiny, fill=theme.FAINT)

    # Status line.
    y = 330
    d.line((left, y - 6, right, y - 6), fill=CYAN_DIM)
    up = f"▲{rate(s.net_up)}  ▼{rate(s.net_down)}"
    d.text((left, y), up, font=small, fill=CYAN)
    d.text((right, y), f"SWAP {gib(s.swap_used)}G", font=small, fill=theme.DIM, anchor="ra")
    status = f"UP {draw.until(s.uptime_s)}  PROC {s.procs}  DISK {s.disk_pct:.0f}%"
    d.text((left, y + 22), draw.clip(d, status, tiny, right - left), font=tiny, fill=theme.FAINT)


register(Tile("system", "System", 360, render, sources=(SystemLoad,)))
