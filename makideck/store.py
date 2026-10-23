"""The shared state and the sources that fill it.

Each Source is a daemon thread polling one thing on its own interval. A
failing poll leaves the last good data in place and flags it stale; a source
can be poked to poll right away (its settings changed).
"""
from __future__ import annotations

import copy
import logging
import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

from .state import DeckState

log = logging.getLogger(__name__)


class Store:
    def __init__(self, state: DeckState | None = None) -> None:
        self._state = state or DeckState()
        self._lock = threading.Lock()

    def snapshot(self) -> DeckState:
        with self._lock:
            snap = copy.copy(self._state)
        snap.now = datetime.now()
        return snap

    def set(self, **sections) -> None:
        with self._lock:
            for name, value in sections.items():
                setattr(self._state, name, value)

    def edit(self, fn: Callable[[DeckState], None]) -> None:
        """Read-modify-write under the lock."""
        with self._lock:
            fn(self._state)

    def mark_stale(self, *names: str) -> None:
        def go(state: DeckState) -> None:
            for name in names:
                setattr(state, name, replace(getattr(state, name), stale=True))
        self.edit(go)


class Source(threading.Thread):
    """Subclasses set `every` (seconds) and implement poll()."""

    every = 60.0
    sections: tuple[str, ...] = ()      # what goes stale when poll() fails

    def __init__(self, store: Store) -> None:
        super().__init__(name=type(self).__name__, daemon=True)
        self.store = store
        self._wake = threading.Event()
        self._done = False

    def poll(self) -> None:
        raise NotImplementedError

    def wait_s(self) -> float:
        """Seconds until the next poll; override to back off."""
        return self.every

    def run(self) -> None:
        while not self._done:
            try:
                self.poll()
            except Exception as e:
                log.warning("%s: %s", self.name, e, exc_info=log.isEnabledFor(logging.DEBUG))
                if self.sections:
                    self.store.mark_stale(*self.sections)
            self._wake.wait(self.wait_s())
            self._wake.clear()

    def poke(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._done = True
        self._wake.set()
