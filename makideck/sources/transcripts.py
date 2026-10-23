"""What Claude Code is up to, from its session transcripts.

Claude Code appends one JSON object per line to
~/.claude/projects/<project>/<session>.jsonl. Every few seconds we read just
the new bytes of the files touched today and keep today's assistant turns;
`summarize` turns them into the Work section (pure, so it's easy to test).
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from ..state import Work
from ..store import Source

ROOT = Path.home() / ".claude" / "projects"
ACTIVE_FOR = timedelta(minutes=2)     # a session counts as live this long
RATE_WINDOW = timedelta(minutes=10)   # tokens/min is averaged over this
_BLOCK = 4 << 20

# Model id prefix → short name; more specific prefixes first.
MODEL_NAMES = (
    ("claude-fable-5-1", "Fable 5.1"), ("claude-fable-5", "Fable 5"),
    ("claude-opus-5-5", "Opus 5.5"), ("claude-opus-5", "Opus 5"),
    ("claude-sonnet-5-5", "Sonnet 5.5"), ("claude-sonnet-5", "Sonnet 5"),
    ("claude-haiku-5-5", "Haiku 5.5"), ("claude-haiku-4-5", "Haiku 4.5"),
)
_USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens",
               "cache_creation_input_tokens")


def model_name(model_id: str) -> str:
    for prefix, name in MODEL_NAMES:
        if model_id.startswith(prefix):
            return name
    return model_id.removeprefix("claude-")


@dataclass(frozen=True)
class Turn:
    at: datetime          # local, tz-aware
    tokens: int
    model: str
    session: str          # transcript path
    project: str


def parse_turn(line: bytes, session: Path) -> Turn | None:
    """One transcript line → an assistant turn, or None for anything else."""
    if b'"assistant"' not in line:
        return None
    try:
        entry = json.loads(line)
        if entry.get("type") != "assistant":
            return None
        at = datetime.fromisoformat(entry["timestamp"]).astimezone()
    except (ValueError, KeyError, TypeError):
        return None
    message = entry.get("message") or {}
    usage = message.get("usage") or {}
    cwd = entry.get("cwd")
    return Turn(at=at,
                tokens=sum(int(usage.get(k) or 0) for k in _USAGE_KEYS),
                model=message.get("model") or "",
                session=str(session),
                project=Path(cwd).name if cwd else session.parent.name)


def summarize(turns: list[Turn], now: datetime) -> Work:
    if not turns:
        return Work(hourly=[0] * (now.hour + 1))
    last = max(turns, key=lambda t: t.at)
    live = {t.session for t in turns if now - t.at < ACTIVE_FOR}
    recent = sum(t.tokens for t in turns if now - t.at < RATE_WINDOW)
    hourly = [0] * (now.hour + 1)
    projects: Counter[str] = Counter()
    models: Counter[str] = Counter()
    for t in turns:
        if t.at.hour < len(hourly):
            hourly[t.at.hour] += t.tokens
        projects[t.project] += t.tokens
        if t.model and not t.model.startswith("<"):        # <synthetic>
            models[model_name(t.model)] += t.tokens
    return Work(
        project=last.project, model=model_name(last.model) if last.model else "",
        active=now - last.at < ACTIVE_FOR, last_at=last.at,
        tokens_per_min=recent / (RATE_WINDOW.total_seconds() / 60),
        live_sessions=len(live), sessions_today=len({t.session for t in turns}),
        hourly=hourly,
        by_project=[kv for kv in projects.most_common() if kv[1]],
        by_model=[kv for kv in models.most_common() if kv[1]],
    )


class Transcripts(Source):
    every = 5.0
    sections = ("work",)

    def __init__(self, store, root: Path = ROOT) -> None:
        super().__init__(store)
        self.root = root
        self._day = None
        self._read_to: dict[Path, int] = {}
        self._turns: list[Turn] = []

    def poll(self) -> None:
        now = datetime.now().astimezone()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if self._day != midnight.date():           # a new day starts empty
            self._day, self._read_to, self._turns = midnight.date(), {}, []
        for path in self.root.glob("*/*.jsonl"):
            try:
                if path.stat().st_mtime >= midnight.timestamp():
                    self._read_new(path, midnight)
            except OSError:
                continue
        self.store.set(work=summarize(self._turns, now))

    def _read_new(self, path: Path, midnight: datetime) -> None:
        pos = self._read_to.get(path, 0)
        if path.stat().st_size <= pos:
            return
        tail = b""
        with path.open("rb") as f:            # in blocks: transcripts get big
            f.seek(pos)
            while block := f.read(_BLOCK):
                lines = (tail + block).split(b"\n")
                tail = lines.pop()            # a half-written last line waits
                for line in lines:
                    turn = parse_turn(line, path)
                    if turn and turn.at >= midnight:
                        self._turns.append(turn)
                pos += len(block)
        self._read_to[path] = pos - len(tail)
