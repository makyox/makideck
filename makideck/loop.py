"""The render loop: state → frame → panel (and the browser mirror).

Normally a frame every 1/fps. While a tile animates (music playing) the loop
runs at live_fps, but the dashboard itself is still rebuilt only every 1/fps
and cached; each fast frame is that copy plus the tiles' live layers.

The panel comes and goes (unplugged, Mac asleep, firmware hiccup): any error
closes it and reconnects with backoff up to a minute. Frames keep flowing to
the mirror meanwhile.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime

from PIL import Image, ImageEnhance

from . import deck
from .config import Config
from .render import dashboard
from .ui import Controls

log = logging.getLogger(__name__)

MIRROR_EVERY_S = 0.25


class _Cached:
    def __init__(self) -> None:
        self.img: Image.Image | None = None
        self.key = None
        self.at = 0.0

    def dashboard(self, state, size, max_age: float) -> Image.Image:
        key = (size, deck.version)
        if self.img is None or key != self.key or time.time() - self.at >= max_age:
            self.img = dashboard.dashboard(state, size, live=False)
            self.key, self.at = key, time.time()
        return self.img.copy()


def compose(state, cfg: Config, ui: Controls, size, cache: _Cached) -> Image.Image:
    if ui.power == "sleep":
        return Image.new("RGB", size)
    night = ui.power == "auto" and cfg.night.now(datetime.now().time())
    view = ui.view
    if night and cfg.night.mode == "off" and view is None:
        return Image.new("RGB", size)
    if view is None:
        img = cache.dashboard(state, size, 1 / cfg.fps)
        dashboard.paint(img, state)
    else:
        img = dashboard.frame(state, size, view)
    if night and cfg.night.mode == "dim":
        img = ImageEnhance.Brightness(img).enhance(cfg.night.dim)
    return img


def run(store, cfg: Config, ui: Controls, panel=None, mirror=None,
        seconds: float = 0) -> None:
    size = dashboard.SIZE
    cache = _Cached()
    retry_at, backoff = 0.0, 1.0
    mirrored = (0.0, None)
    stop_at = time.time() + seconds if seconds else None
    try:
        while stop_at is None or time.time() < stop_at:
            started = time.time()
            if panel is not None and not panel.open and started >= retry_at:
                try:
                    size = panel.connect()
                    backoff = 1.0
                except Exception as e:
                    log.warning("panel: %s — retrying in %.0fs", e, backoff)
                    retry_at, backoff = started + backoff, min(backoff * 2, 60.0)

            ui.wake.clear()
            state = store.snapshot()
            img = compose(state, cfg, ui, size, cache)
            if mirror is not None and (started - mirrored[0] >= MIRROR_EVERY_S
                                       or ui.view != mirrored[1]):
                mirror.publish(img, state)
                mirrored = (started, ui.view)
            if panel is not None and panel.open:
                try:
                    if not panel.show(img):
                        raise RuntimeError("frame not accepted")
                except Exception as e:
                    log.warning("panel: %s — reconnecting", e)
                    panel.close()
                    continue
            live = ui.view is None and ui.power != "sleep" and dashboard.animated(state)
            fps = cfg.live_fps if live else cfg.fps
            ui.wake.wait(max(0.0, 1 / fps - (time.time() - started)))
    finally:
        if panel is not None:
            panel.close()
