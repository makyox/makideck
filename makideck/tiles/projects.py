"""Projects today: where today's tokens went, plus the split between models."""
from __future__ import annotations

from ..deck import Ctx, Field, Tile, register
from ..render import draw, theme
from ..sources.transcripts import Transcripts


def render(c: Ctx) -> None:
    d, work = c.d, c.state.work
    d.text((c.left, 26), "PROJECTS TODAY", font=theme.sans(18),
           fill=theme.STALE if work.stale else theme.DIM)
    rows = work.by_project[: int(c.settings.get("rows", 5))]
    if not rows:
        d.text((c.left, 66), "—", font=theme.mono(22), fill=theme.FAINT)
    top = rows[0][1] if rows else 1
    y = 62
    for i, (name, n) in enumerate(rows):
        amount = draw.tokens(n)
        name_font, amount_font = theme.mono(20), theme.mono(19)
        room = c.right - c.left - d.textlength(amount, font=amount_font) - 16
        d.text((c.left, y), draw.clip(d, name, name_font, room), font=name_font,
               fill=theme.TEXT if i == 0 else theme.DIM)
        d.text((c.right, y + 1), amount, font=amount_font, fill=theme.TEXT, anchor="ra")
        draw.meter(d, (c.left, y + 28, c.right, y + 34), 100 * n / top,
                   theme.ACCENT if i == 0 else theme.FAINT)
        y += 46

    models = work.by_model[: len(theme.SERIES)]
    total = sum(n for _, n in models)
    if not total:
        return
    y = max(y + 4, 300)
    d.text((c.left, y), "MODELS", font=theme.sans(15), fill=theme.FAINT)
    draw.split_bar(d, (c.left + 80, y + 4, c.right, y + 14),
                   [(n / total, col) for (_, n), col in zip(models, theme.SERIES, strict=False)])
    x, legend = c.left, theme.mono(16)
    for (name, n), col in zip(models, theme.SERIES, strict=False):
        label = f"{name} {100 * n / total:.0f}%"
        w = 16 + d.textlength(label, font=legend)
        if x + w > c.right:
            break
        d.ellipse((x, y + 33, x + 10, y + 43), fill=col)
        d.text((x + 16, y + 28), label, font=legend, fill=theme.DIM)
        x += w + 24


register(Tile("projects", "Projects today", 400, render, sources=(Transcripts,),
              fields=(Field("rows", "Projects shown", "select", ("3", "4", "5")),),
              defaults={"rows": "5"}))
