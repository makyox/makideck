"""Claude Code: plan usage (session + week) and today's spend."""
from __future__ import annotations

from ..deck import Ctx, Tile, register
from ..render import draw, theme
from ..sources.ccusage import CcusageSpend
from ..sources.claude_limits import ClaudeLimits
from ..sources.transcripts import Transcripts
from ..state import Limit


def _window(c: Ctx, name: str, lim: Limit | None, y: int, stale: bool) -> None:
    d = c.d
    d.text((c.left, y), name, font=theme.sans(22), fill=theme.DIM)
    if lim is None:
        d.text((c.right, y), "—", font=theme.mono(24), fill=theme.FAINT, anchor="ra")
        return
    color = theme.STALE if stale else theme.usage_color(lim.pct)
    d.text((c.right, y - 10), f"{lim.pct:.0f}%", font=theme.mono(38), fill=color, anchor="ra")
    draw.meter(d, (c.left, y + 34, c.right, y + 52), lim.pct, color)
    if lim.resets_at:
        left = (lim.resets_at - c.state.now).total_seconds()
        d.text((c.left, y + 60), f"resets {lim.resets_at:%H:%M} · {draw.until(left)}",
               font=theme.mono(17), fill=theme.FAINT)


def render(c: Ctx) -> None:
    d, s = c.d, c.state
    spend, lim = s.spend, s.limits
    d.text((c.left, 26), "CLAUDE CODE", font=theme.sans(30), fill=theme.ACCENT)
    d.text((c.right, 22), f"${spend.today_usd:,.2f}", font=theme.sans(34),
           fill=theme.STALE if spend.stale else theme.TEXT, anchor="ra")
    note = "today · API prices"
    stale = [n for n, flag in (("usage", lim.stale), ("spend", spend.stale)) if flag]
    if stale:
        note += f" · {'/'.join(stale)} stale"
    d.text((c.right, 62), note, font=theme.sans(15), fill=theme.FAINT, anchor="ra")

    _window(c, "SESSION", lim.session, 98, lim.stale)
    _window(c, "WEEK", lim.week, 194, lim.stale)

    d.line((c.left, 292, c.right, 292), fill=theme.LINE)
    width = c.right - c.left
    rows = (
        (f"{draw.tokens(spend.today_tokens)} tok · {s.work.sessions_today} sessions", 18, theme.TEXT),
        (f"in {draw.tokens(spend.input_tokens)} · out {draw.tokens(spend.output_tokens)}"
         f" · cache {draw.tokens(spend.cache_tokens)}", 16, theme.DIM),
        (f"week {draw.tokens(spend.week_tokens)} · ${spend.week_usd:,.0f}", 16, theme.DIM),
    )
    for y, (text, size, color) in zip((304, 330, 354), rows, strict=True):
        d.text((c.left, y), text, font=draw.shrink(d, text, "mono", size, width), fill=color)


register(Tile("claude", "Claude Code", 460, render,
              sources=(ClaudeLimits, CcusageSpend, Transcripts)))
