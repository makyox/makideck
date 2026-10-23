"""Claude plan usage: the 5-hour session and weekly windows.

Asks the same endpoint Claude Code's /usage screen uses, authenticated with
Claude Code's own OAuth token, read from the macOS Keychain on every poll
(Claude Code refreshes it now and then). Read-only; the token is only ever
sent to api.anthropic.com.

The endpoint rate-limits eagerly, so polls are every 2 minutes and a 429
backs off (honouring Retry-After) up to 15 minutes.
"""
from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from datetime import datetime

from ..state import Limit, Limits
from ..store import Source

URL = "https://api.anthropic.com/api/oauth/usage"
KEYCHAIN_ITEM = "Claude Code-credentials"
MAX_BACKOFF_S = 900.0


def oauth_token() -> str:
    raw = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_ITEM, "-w"],
        capture_output=True, text=True, timeout=10, check=True).stdout
    return json.loads(raw)["claudeAiOauth"]["accessToken"]


def parse_usage(data: dict) -> Limits:
    def window(key: str) -> Limit | None:
        w = data.get(key)
        if not w:
            return None
        resets = None
        if w.get("resets_at"):
            try:
                resets = datetime.fromisoformat(w["resets_at"]).astimezone().replace(tzinfo=None)
            except ValueError:
                pass
        return Limit(pct=float(w.get("utilization") or 0), resets_at=resets)
    return Limits(session=window("five_hour"), week=window("seven_day"))


class ClaudeLimits(Source):
    every = 120.0
    sections = ("limits",)

    def __init__(self, store) -> None:
        super().__init__(store)
        self._backoff = 0.0

    def wait_s(self) -> float:
        return self._backoff or self.every

    def poll(self) -> None:
        req = urllib.request.Request(URL, headers={
            "Authorization": f"Bearer {oauth_token()}",
            "anthropic-beta": "oauth-2025-04-20",
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                limits = parse_usage(json.load(resp))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry = float(e.headers.get("Retry-After") or 0)
                self._backoff = min(MAX_BACKOFF_S,
                                    max(retry, 2 * (self._backoff or self.every)))
                raise RuntimeError(f"rate limited, next try in {self._backoff:.0f}s") from None
            raise
        self._backoff = 0.0
        self.store.set(limits=limits)
