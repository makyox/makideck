"""Tokens and their API-price equivalent, from ccusage (runs via npx).

ccusage already handles deduplication and per-model pricing of Claude Code's
transcripts; we ask it for this week by day and keep today + the week total.
"""
from __future__ import annotations

import json
import subprocess
from datetime import date, timedelta

from ..state import Spend
from ..store import Source

# Pinned: 20.0.39 ships without a darwin-arm64 binary. Bump after checking.
CCUSAGE = "ccusage@20.0.38"


def parse_daily(data: dict, today: date) -> Spend:
    spend = Spend()
    for row in data.get("daily", []):
        spend.week_tokens += row.get("totalTokens", 0)
        spend.week_usd += row.get("totalCost", 0.0)
        if row.get("period", row.get("date")) == today.isoformat():
            spend.today_tokens = row.get("totalTokens", 0)
            spend.today_usd = row.get("totalCost", 0.0)
            spend.input_tokens = row.get("inputTokens", 0)
            spend.output_tokens = row.get("outputTokens", 0)
            spend.cache_tokens = (row.get("cacheReadTokens", 0)
                                  + row.get("cacheCreationTokens", 0))
    return spend


class CcusageSpend(Source):
    every = 60.0
    sections = ("spend",)

    def poll(self) -> None:
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        out = subprocess.run(
            ["npx", "-y", CCUSAGE, "daily", "--json", "--since", f"{monday:%Y%m%d}"],
            capture_output=True, text=True, timeout=180, check=True).stdout
        self.store.set(spend=parse_daily(json.loads(out), today))
