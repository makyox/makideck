"""Local web server: the live mirror (/), the editor (/editor) and their API.

The panel has no touch, so the mirror is the remote: click a zone and the
panel reacts. Bound to 127.0.0.1 unless you choose otherwise in config.toml.

    GET  /frame.jpg  /state  /deck  /cities?q=
    POST /tap {x,y}  /view {view}  /power {mode}
         /deck/order {order | reset}  /deck/settings/<tile> {...}
"""
from __future__ import annotations

import io
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import parse_qs, urlsplit

from . import deck
from .render import dashboard
from .ui import Controls

log = logging.getLogger(__name__)
PAGES = files("makideck") / "web"
ASSETS = files("makideck") / "assets"


class Mirror:
    """The latest frame as JPEG, plus the state it was drawn from."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.jpeg, self.size, self.seq, self.state = b"", (0, 0), 0, None

    def publish(self, img, state) -> None:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=85)
        with self._lock:
            self.jpeg, self.size, self.state = buf.getvalue(), img.size, state
            self.seq += 1

    def latest(self):
        with self._lock:
            return self.jpeg, self.size, self.seq, self.state


def serve(mirror: Mirror, ui: Controls, host: str, port: int):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args) -> None:
            log.debug(fmt, *args)

        def reply(self, body: bytes, ctype: str = "application/json", code: int = 200) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def json(self, data, code: int = 200) -> None:
            self.reply(json.dumps(data, ensure_ascii=False).encode(), code=code)

        def status(self) -> dict:
            _, size, seq, state = mirror.latest()
            view = ui.view
            zones = dashboard.tap_zones(state, size, view) if state else []
            return {"size": size, "seq": seq, "view": view, "zones": zones,
                    "power": ui.power, "order": deck.order(), "version": deck.version}

        def do_GET(self) -> None:
            url = urlsplit(self.path)
            if url.path in ("/", "/editor"):
                page = "mirror.html" if url.path == "/" else "editor.html"
                self.reply((PAGES / page).read_bytes(), "text/html; charset=utf-8")
            elif url.path.startswith("/assets/") and url.path.endswith(".png"):
                asset = ASSETS / url.path.rsplit("/", 1)[1]
                if asset.is_file():
                    self.reply(asset.read_bytes(), "image/png")
                else:
                    self.reply(b"not found", "text/plain", 404)
            elif url.path == "/frame.jpg":
                jpeg = mirror.latest()[0]
                self.reply(jpeg, "image/jpeg", 200 if jpeg else 503)
            elif url.path == "/state":
                self.json(self.status())
            elif url.path == "/deck":
                self.json(deck.to_json())
            elif url.path == "/cities":
                from .sources.outside import find_cities
                q = parse_qs(url.query).get("q", [""])[0].strip()
                try:
                    self.json({"results": find_cities(q) if len(q) > 1 else []})
                except Exception as e:
                    log.warning("city search %r: %s", q, e)
                    self.json({"results": [], "error": str(e)})
            else:
                self.reply(b"not found", "text/plain", 404)

        def do_POST(self) -> None:
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            except ValueError:
                return self.json({"errors": ["bad json"]}, 400)
            path = urlsplit(self.path).path
            if path == "/tap":
                _, size, _, state = mirror.latest()
                action = ui.tap(state, size, int(body.get("x", -1)), int(body.get("y", -1))) if state else None
                self.json({"action": action, **self.status()})
            elif path == "/view":
                ui.show(body.get("view"))
                self.json(self.status())
            elif path == "/power":
                ok = ui.set_power(str(body.get("mode")))
                self.json(self.status(), 200 if ok else 400)
            elif path == "/deck/order":
                ok = ui.set_order(None if body.get("reset") else body.get("order"))
                self.json(deck.to_json() if ok else {"errors": ["unknown tiles"]}, 200 if ok else 400)
            elif path.startswith("/deck/settings/"):
                errors = ui.set_settings(path.rsplit("/", 1)[1], body)
                self.json({"errors": errors} if errors else deck.to_json(), 400 if errors else 200)
            else:
                self.reply(b"not found", "text/plain", 404)

    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=server.serve_forever, name="web", daemon=True).start()
    log.info("mirror on http://%s:%d/  editor on /editor", host, port)
    return server
