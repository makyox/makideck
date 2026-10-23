"""The deck: tiles, their order on the panel, and their settings.

A tile is one column of the panel above the footer. Everything a tile needs
is declared on it — how it draws, which sources feed it, which settings it
has (the editor builds the form from `fields`) — so a new module is one file
with one `register(Tile(...))`. Built-in tiles live in makideck/tiles/;
your own go in ~/.config/makideck/tiles/*.py and are loaded at start.

Tiles keep their natural width relative to each other; the visible ones are
stretched together to fill the panel. The order, which tiles are hidden and
each tile's settings are saved to ~/.config/makideck/deck.json.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import pkgutil
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .state import DeckState

log = logging.getLogger(__name__)

Box = tuple[int, int, int, int]
CONFIG_DIR = Path.home() / ".config" / "makideck"
DECK_FILE = CONFIG_DIR / "deck.json"
PLUGIN_DIR = CONFIG_DIR / "tiles"


@dataclass
class Ctx:
    """What a tile gets to draw with: its column [x0, x1) × [top, bottom)."""
    d: ImageDraw.ImageDraw
    img: Image.Image
    state: DeckState
    x0: int
    x1: int
    top: int
    bottom: int
    settings: dict
    pad: int = 28

    @property
    def left(self) -> int:          # content edges, inside the padding
        return self.x0 + self.pad

    @property
    def right(self) -> int:
        return self.x1 - self.pad


@dataclass(frozen=True)
class Field:
    """One setting in the editor. kind: text | number | select | toggle, or
    the special city | quotes pickers. `options` feeds select."""
    key: str
    label: str
    kind: str = "text"
    options: tuple[str, ...] = ()
    hint: str = ""


@dataclass(frozen=True)
class Tile:
    id: str
    name: str
    width: int
    draw: Callable[[Ctx], None]
    # Optional:
    sources: tuple[type, ...] = ()              # store.Source subclasses it needs
    fields: tuple[Field, ...] = ()
    defaults: dict = field(default_factory=dict)
    check: Callable[[dict], tuple[dict, list[str]]] | None = None   # validate settings
    taps: Callable[[Ctx], dict[str, Box]] | None = None   # "open:<view>" or own actions
    on_tap: Callable[[str], None] | None = None
    # Live layer repainted every frame over the cached dashboard (e.g. a
    # visualizer) and whether it currently wants the high frame rate.
    paint: Callable[[Ctx, float], None] | None = None
    animated: Callable[[DeckState], bool] | None = None


_lock = threading.RLock()
REGISTRY: dict[str, Tile] = {}
_order: list[str] = []          # visible tiles, left to right
_settings: dict[str, dict] = {}
_listeners: list[Callable[[str], None]] = []
version = 0                     # bumped on any change; caches compare it


def register(tile: Tile) -> Tile:
    global version
    with _lock:
        REGISTRY[tile.id] = tile
        version += 1
    return tile


# Built-ins shown out of the box, in this order; other tiles start hidden.
DEFAULT_ORDER = ("claude", "spotify", "projects", "session", "outside")


def order() -> list[str]:
    with _lock:
        return [t for t in _order if t in REGISTRY]


def hidden() -> list[str]:
    with _lock:
        return [t for t in REGISTRY if t not in _order]


def set_order(ids: list[str]) -> bool:
    """Show these tiles in this order (the rest hidden); False if unknown ids."""
    global version
    if not ids or len(set(ids)) != len(ids) or any(i not in REGISTRY for i in ids):
        return False
    with _lock:
        _order[:] = ids
        version += 1
    _changed("*")
    return True


def reset_order() -> None:
    set_order([t for t in DEFAULT_ORDER if t in REGISTRY] or list(REGISTRY)[:1])


def columns(width: int) -> list[tuple[Tile, int, int]]:
    """(tile, x0, x1) for the visible tiles, stretched to fill width."""
    tiles = [REGISTRY[i] for i in order()]
    total = sum(t.width for t in tiles) or 1
    out, x = [], 0.0
    for t in tiles:
        x1 = x + width * t.width / total
        out.append((t, round(x), round(x1)))
        x = x1
    return out


def settings(tile_id: str) -> dict:
    with _lock:
        t = REGISTRY.get(tile_id)
        return {**(t.defaults if t else {}), **_settings.get(tile_id, {})}


def update_settings(tile_id: str, values: dict) -> tuple[dict, list[str]]:
    """Validate (tile.check) and store; returns (saved values, errors)."""
    global version
    t = REGISTRY[tile_id]
    clean, errors = t.check(values) if t.check else (values, [])
    if errors:
        return clean, errors
    with _lock:
        _settings[tile_id] = {**_settings.get(tile_id, {}), **clean}
        version += 1
    _changed(tile_id)
    return settings(tile_id), []


def on_change(fn: Callable[[str], None]) -> None:
    """fn(tile_id) after a tile's settings change ("*" for the layout)."""
    _listeners.append(fn)


def _changed(tile_id: str) -> None:
    for fn in list(_listeners):
        try:
            fn(tile_id)
        except Exception:
            log.exception("deck listener failed")


def save(path: Path = DECK_FILE) -> None:
    with _lock:
        data = {"order": list(_order), "settings": dict(_settings)}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def load(path: Path = DECK_FILE) -> None:
    global version
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return
    except (OSError, ValueError) as e:
        log.warning("ignoring %s: %s", path, e)
        return
    with _lock:
        saved = data.get("settings") or {}
        _settings.update({k: v for k, v in saved.items() if isinstance(v, dict)})
        known = [i for i in data.get("order") or [] if i in REGISTRY]
        if known:
            _order[:] = known
        version += 1


def load_tiles(plugin_dir: Path = PLUGIN_DIR) -> None:
    """Import the built-in tiles, then the user's own."""
    from . import tiles
    for mod in pkgutil.iter_modules(tiles.__path__):
        importlib.import_module(f"{tiles.__name__}.{mod.name}")
    for path in sorted(plugin_dir.glob("*.py")) if plugin_dir.is_dir() else []:
        try:
            spec = importlib.util.spec_from_file_location(f"makideck_user_{path.stem}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            log.info("loaded tile module %s", path)
        except Exception:
            log.exception("tile module %s failed to load", path)
    reset_order()


def sources() -> list[type]:
    """Source classes the visible tiles need, without duplicates."""
    seen: list[type] = []
    for tid in order():
        for src in REGISTRY[tid].sources:
            if src not in seen:
                seen.append(src)
    return seen


def to_json() -> dict[str, Any]:
    """Everything the editor shows."""
    return {
        "order": order(), "hidden": hidden(), "default": list(DEFAULT_ORDER),
        "tiles": [{"id": t.id, "name": t.name, "width": t.width,
                   "fields": [vars(f) for f in t.fields],
                   "settings": settings(t.id)} for t in REGISTRY.values()],
    }
