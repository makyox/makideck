"""Settings that aren't about tiles, from ~/.config/makideck/config.toml.

Everything is optional; a broken file is logged and ignored (the deck is an
appliance, it should come up). See config.example.toml.
"""
from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

from .deck import CONFIG_DIR

log = logging.getLogger(__name__)

CONFIG_FILE = CONFIG_DIR / "config.toml"
LOG_DIR = Path.home() / "Library" / "Logs" / "makideck"


@dataclass
class Night:
    """Quiet hours: mode "on" ignores them, "dim" darkens, "off" blanks."""
    mode: str = "on"
    start: time = time(0, 0)
    end: time = time(7, 0)
    dim: float = 0.3

    def now(self, t: time) -> bool:
        if self.mode == "on":
            return False
        if self.start <= self.end:
            return self.start <= t < self.end
        return t >= self.start or t < self.end          # across midnight


@dataclass
class Config:
    fps: float = 2.0             # dashboard refresh
    live_fps: float = 15.0       # while a tile animates (the panel takes ~24)
    quality: int = 90            # JPEG
    web_host: str = "127.0.0.1"
    web_port: int = 8787
    night: Night = field(default_factory=Night)


def load(path: Path = CONFIG_FILE) -> Config:
    cfg = Config()
    if not path.exists():
        return cfg
    try:
        raw = tomllib.loads(path.read_text())
        for key in ("fps", "live_fps", "quality", "web_host", "web_port"):
            if key in raw:
                setattr(cfg, key, type(getattr(cfg, key))(raw[key]))
        n = raw.get("night") or {}
        cfg.night = Night(mode=n.get("mode", "on"),
                          start=time.fromisoformat(n.get("start", "00:00")),
                          end=time.fromisoformat(n.get("end", "07:00")),
                          dim=float(n.get("dim", 0.3)))
    except (OSError, ValueError, TypeError, tomllib.TOMLDecodeError) as e:
        log.warning("ignoring %s: %s", path, e)
        return Config()
    return cfg

