"""makideck — command line.

    makideck run [--demo] [--no-panel]   the deck: sources → panel + web (:8787)
    makideck preview [out.png] [--view forecast] [--live]
    makideck menubar                     the menu bar icon (it runs the deck)
    makideck login on|off                open the menu bar app at login
"""
from __future__ import annotations

import argparse
import logging
import logging.handlers
import signal
import time
from pathlib import Path

from . import deck
from .config import LOG_DIR, language, load


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="makideck", description="A desk deck for Claude Code.")
    ap.add_argument("-v", "--verbose", action="store_true")
    cmd = ap.add_subparsers(dest="cmd", required=True)
    run = cmd.add_parser("run", help="drive the panel and serve the editor")
    run.add_argument("--demo", action="store_true", help="made-up data, no sources")
    run.add_argument("--no-panel", action="store_true", help="web only, leave the USB panel alone")
    run.add_argument("--port", type=int, help="web port (default from config, 8787)")
    run.add_argument("--seconds", type=float, default=0, help="stop after this long")
    pre = cmd.add_parser("preview", help="render one frame to a PNG")
    pre.add_argument("out", nargs="?", default="preview.png")
    pre.add_argument("--view", help="a full-screen view instead, e.g. forecast")
    pre.add_argument("--live", action="store_true", help="real data (waits for sources)")
    cmd.add_parser("menubar", help="menu bar icon that runs the deck")
    login = cmd.add_parser("login", help="open the menu bar app at login")
    login.add_argument("state", choices=("on", "off"))
    args = ap.parse_args(argv)

    cfg = load()
    _logging(args.verbose, to_file=args.cmd == "run" and not args.demo)
    if args.cmd == "menubar":
        from .menubar import run as menubar
        menubar()
        return 0
    if args.cmd == "login":
        from . import launchagent
        launchagent.install() if args.state == "on" else launchagent.uninstall()
        print(f"makideck at login: {args.state}")
        return 0

    deck.load_tiles()
    if not getattr(args, "demo", False):
        deck.load()
    if args.cmd == "preview":
        return _preview(args)
    return _run(args, cfg)


def _preview(args) -> int:
    from .render import dashboard
    from .state import demo_state
    state = demo_state()
    if args.live:
        store = _start_sources()
        time.sleep(20)                # ccusage's first run is slow
        state = store.snapshot()
    dashboard.frame(state, dashboard.SIZE, args.view).save(args.out)
    print(f"wrote {args.out}")
    return 0


def _run(args, cfg) -> int:
    from . import audio, loop
    from .device import Panel
    from .render.viz import VIZ
    from .server import Mirror, serve
    from .state import demo_state
    from .store import Store
    from .ui import Controls

    def terminate(*_):                # menu bar Stop → a clean panel close
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate)

    if args.demo:
        store = Store(demo_state())
    else:
        store = _start_sources()
        listener = audio.Analyzer()
        if listener.start():
            VIZ.audio = listener
    ui = Controls(persist=not args.demo)
    mirror = Mirror()
    serve(mirror, ui, cfg.web_host, args.port or cfg.web_port, language(cfg))
    try:
        loop.run(store, cfg, ui, panel=None if args.no_panel else Panel(cfg.quality),
                 mirror=mirror, seconds=args.seconds)
    except KeyboardInterrupt:
        pass
    return 0


def _start_sources():
    """The sources the visible tiles need; a tile shown later starts its own."""
    from .store import Store
    store, running = Store(), {}

    def ensure(_tile_id: str = "*") -> None:
        for cls in deck.sources():
            if cls not in running:
                running[cls] = cls(store)
                running[cls].start()
    ensure()
    deck.on_change(ensure)
    return store


def _logging(verbose: bool, to_file: bool) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if to_file:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.handlers.RotatingFileHandler(
            Path(LOG_DIR) / "makideck.log", maxBytes=1_000_000, backupCount=3))
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")


if __name__ == "__main__":
    raise SystemExit(main())
