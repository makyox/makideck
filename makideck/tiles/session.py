"""Session: is Claude working right now, on what, with which model, how fast."""
from __future__ import annotations

from ..deck import Ctx, Tile, register
from ..render import draw, theme
from ..sources.transcripts import Transcripts


def render(c: Ctx) -> None:
    d, w = c.d, c.state.work
    d.text((c.left, 26), "SESSION" + (" (stale)" if w.stale else ""), font=theme.sans(18),
           fill=theme.STALE if w.stale else theme.DIM)
    color = theme.GOOD if w.active else theme.FAINT
    d.ellipse((c.left, 67, c.left + 18, 85), fill=color)
    status = "ACTIVE" if w.active else "IDLE"
    if w.active and w.live_sessions > 1:
        status += f" · {w.live_sessions} sessions"
    d.text((c.left + 30, 64), status, font=theme.sans(22),
           fill=theme.GOOD if w.active else theme.DIM)
    y = 110
    if w.project:
        f = theme.mono(24)
        d.text((c.left, y), draw.clip(d, w.project, f, c.right - c.left), font=f, fill=theme.TEXT)
        y += 38
    if w.model:
        d.text((c.left, y), w.model, font=theme.sans(20), fill=theme.ACCENT)
        y += 34
    if w.active and w.tokens_per_min:
        d.text((c.left, y), f"{draw.tokens(w.tokens_per_min)} tok/min",
               font=theme.mono(20), fill=theme.DIM)
    elif w.last_at and not w.active:
        ago = (c.state.now.astimezone() - w.last_at).total_seconds()
        d.text((c.left, y), f"last reply {draw.until(ago)} ago",
               font=theme.mono(18), fill=theme.FAINT)


register(Tile("session", "Session", 330, render, sources=(Transcripts,)))
