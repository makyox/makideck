"""The menu bar icon: start/stop the deck, sleep the panel, open the editor.

The deck runs as a child process (`makideck run`), so the icon survives the
deck crashing and vice versa. Status and controls go through the deck's web
API. On launch it starts the deck unless a working one is already running.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request

import rumps

from . import launchagent
from .config import LOG_DIR
from .config import load as load_config

log = logging.getLogger(__name__)

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
RUN_MATCH = "makideck run"

T = {"starting": "starting…", "on": "running", "asleep": "panel asleep", "awake": "running (never sleeps)",
     "off": "stopped", "busy": "one moment…", "start": "Start", "stop": "Stop", "restart": "Restart",
     "auto": "Sleep at night (auto)", "sleep": "Sleep now", "wake": "Never sleep",
     "editor": "Edit deck…", "mirror": "Live view in browser", "logs": "Show logs",
     "login": "Open at login", "quit": "Quit makideck"}


def deck_pids() -> list[int]:
    out = subprocess.run(["pgrep", "-f", RUN_MATCH], capture_output=True, text=True).stdout
    return [int(p) for p in out.split() if int(p) != os.getpid()]


class Menu(rumps.App):
    def __init__(self) -> None:
        super().__init__("makideck", icon=self._icon("off"), template=True, quit_button=None)
        cfg = load_config()
        self.api = f"http://127.0.0.1:{cfg.web_port}"
        self.t = t = T
        self.status = rumps.MenuItem("makideck")
        self.toggle = rumps.MenuItem(t["start"], callback=self.on_toggle)
        self.restart = rumps.MenuItem(t["restart"], callback=self.on_restart)
        self.power = {m: rumps.MenuItem(t[m], callback=self.on_power) for m in ("auto", "sleep", "wake")}
        self.login = rumps.MenuItem(t["login"], callback=self.on_login)
        self.menu = [self.status, None, self.toggle, self.restart, None, *self.power.values(), None,
                     rumps.MenuItem(t["editor"], callback=lambda _: self.open("/editor")),
                     rumps.MenuItem(t["mirror"], callback=lambda _: self.open("/")),
                     rumps.MenuItem(t["logs"], callback=self.on_logs), None,
                     self.login, rumps.MenuItem(t["quit"], callback=self.on_quit)]
        self.busy = False
        threading.Thread(target=self.autostart, daemon=True).start()

    @staticmethod
    def _icon(name: str) -> str:
        return os.path.join(ASSETS, f"menubar-{name}.png")

    def call(self, path: str, body: dict | None = None) -> dict | None:
        data = None if body is None else json.dumps(body).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(self.api + path, data=data), timeout=0.5) as r:
                return json.load(r)
        except Exception:
            return None

    def open(self, path: str) -> None:
        subprocess.run(["open", self.api + path])

    # ── the deck process ─────────────────────────────────────────────────
    def autostart(self) -> None:
        time.sleep(2)
        # One that's still shutting down (we were restarted) shows in pgrep
        # but doesn't answer: give it 10 s, then replace it.
        deadline = time.time() + 10
        while deck_pids() and time.time() < deadline:
            if self.call("/state") is not None:
                log.info("deck already running: %s", deck_pids())
                return
            time.sleep(0.5)
        self.stop(grace_s=0)
        self.start()

    def start(self) -> None:
        log.info("starting the deck")
        subprocess.Popen([sys.executable, "-m", "makideck", "run"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    def stop(self, grace_s: float = 5) -> None:
        for pid in deck_pids():
            os.kill(pid, signal.SIGTERM)       # `run` closes the panel cleanly
        deadline = time.time() + grace_s
        while deck_pids() and time.time() < deadline:
            time.sleep(0.2)
        for pid in deck_pids():
            log.info("killing unresponsive deck %s", pid)
            os.kill(pid, signal.SIGKILL)

    def background(self, fn) -> None:
        def go() -> None:
            self.busy = True
            try:
                fn()
            finally:
                self.busy = False
        threading.Thread(target=go, daemon=True).start()

    # ── menu ─────────────────────────────────────────────────────────────
    @rumps.timer(2)
    def refresh(self, _) -> None:
        t, state = self.t, self.call("/state")
        up = state is not None
        starting = not up and bool(deck_pids())
        power = (state or {}).get("power", "auto")
        if self.busy:
            label = t["busy"]
        elif up:
            label = {"sleep": t["asleep"], "wake": t["awake"]}.get(power, t["on"])
        else:
            label = t["starting"] if starting else t["off"]
        self.status.title = f"makideck: {label}"
        self.toggle.title = t["stop"] if up or starting else t["start"]
        self.restart.set_callback(self.on_restart if up else None)
        for mode, item in self.power.items():
            item.state = int(up and power == mode)
            item.set_callback(self.on_power if up else None)
        self.login.state = int(launchagent.installed())
        self.icon = self._icon("off" if not up else "sleep" if power == "sleep" else "on")

    def on_toggle(self, _) -> None:
        if deck_pids():
            self.background(self.stop)
        else:
            self.start()

    def on_restart(self, _) -> None:
        self.background(lambda: (self.stop(), self.start()))

    def on_power(self, item) -> None:
        mode = next(m for m, i in self.power.items() if i is item)
        self.call("/power", {"mode": mode})
        self.refresh(None)

    def on_logs(self, _) -> None:
        subprocess.run(["open", "-a", "Console", str(LOG_DIR / "makideck.log")])

    def on_login(self, _) -> None:
        if launchagent.installed():
            launchagent.uninstall(stop=False)
        else:
            launchagent.install(start=False)
        self.refresh(None)

    def on_quit(self, _) -> None:
        self.stop()
        rumps.quit_application()


def run() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, filename=LOG_DIR / "menubar.log", force=True,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    from Foundation import NSBundle  # no Dock icon: we're a menu bar app
    bundle_info = NSBundle.mainBundle().infoDictionary()
    if bundle_info is not None:
        bundle_info["LSUIElement"] = "1"
    Menu().run()
