"""Example tile: days left until a date you pick in the editor.

Copy this file to ~/.config/makideck/tiles/ and restart makideck; the tile
shows up under "Hidden tiles" in the editor — add it, then click it to set
the date and the label.
"""
from __future__ import annotations

from datetime import date

from makideck.deck import Ctx, Field, Tile, register
from makideck.render import theme


def check(values: dict) -> tuple[dict, list[str]]:
    try:
        date.fromisoformat(str(values.get("date", "")))
    except ValueError:
        return values, ["date: use YYYY-MM-DD"]
    return values, []


def render(c: Ctx) -> None:
    label = c.settings["label"]
    days = (date.fromisoformat(c.settings["date"]) - c.state.now.date()).days
    c.d.text((c.left, 26), label.upper(), font=theme.sans(18), fill=theme.DIM)
    c.d.text((c.left, 70), str(max(days, 0)), font=theme.sans(120), fill=theme.ACCENT)
    c.d.text((c.left, 230), "day to go" if days == 1 else "days to go",
             font=theme.sans(24), fill=theme.TEXT)
    c.d.text((c.left, 270), c.settings["date"], font=theme.mono(18), fill=theme.FAINT)


register(Tile(
    "countdown", "Countdown", 300, render,
    fields=(Field("label", "Label"), Field("date", "Date", hint="YYYY-MM-DD")),
    defaults={"label": "Launch", "date": "2026-12-24"},
    check=check,
))
