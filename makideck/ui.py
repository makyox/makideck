"""What the user changed while the deck runs: an open view, power mode, tile
layout and settings. Shared by the render loop and the web server; every
change sets `wake` so the next frame doesn't wait for the tick.
"""
from __future__ import annotations

import threading
import time

from . import deck
from .render import dashboard, views

VIEW_TIMEOUT_S = 60.0
POWER = ("auto", "sleep", "wake")    # auto follows the night hours


class Controls:
    def __init__(self, view_timeout_s: float = VIEW_TIMEOUT_S, persist: bool = True) -> None:
        self.wake = threading.Event()
        self.power = "auto"
        self._view: tuple[str, float] | None = None
        self._timeout = view_timeout_s
        self._persist = persist

    @property
    def view(self) -> str | None:
        if self._view and time.time() - self._view[1] > self._timeout:
            self._view = None
        return self._view[0] if self._view else None

    def show(self, view: str | None) -> None:
        self._view = (view, time.time()) if view in views.VIEWS else None
        self.wake.set()

    def set_power(self, mode: str) -> bool:
        if mode not in POWER:
            return False
        self.power = mode
        self.wake.set()
        return True

    def tap(self, state, size: tuple[int, int], x: int, y: int) -> str | None:
        zone = dashboard.hit(state, size, self.view, x, y)
        if zone is None:
            return None
        action = zone["action"]
        if action == "close":
            self.show(None)
        elif action.startswith("open:"):
            self.show(action.removeprefix("open:"))
        else:
            tile = deck.REGISTRY.get(zone["tile"])
            if tile and tile.on_tap:
                tile.on_tap(action)
                self._save()
        self.wake.set()
        return action

    def set_order(self, ids: list[str] | None) -> bool:
        if ids is None:
            deck.reset_order()
        elif not deck.set_order(ids):
            return False
        self._save()
        self.wake.set()
        return True

    def set_settings(self, tile_id: str, values: dict) -> list[str]:
        if tile_id not in deck.REGISTRY:
            return [f"no tile {tile_id}"]
        _, errors = deck.update_settings(tile_id, values)
        if not errors:
            self._save()
            self.wake.set()
        return errors

    def _save(self) -> None:
        if self._persist:
            deck.save()
