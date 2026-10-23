"""Spotify: what's playing, over an ASCII flight that moves with the music.

The visualizer is this tile's live layer (`paint`): the dashboard is cached
and only the character box is redrawn every frame while music plays. Tap it
to switch between the tunnel and the starfield.
"""
from __future__ import annotations

import time

from ..deck import Ctx, Field, Tile, register
from ..render import draw, theme
from ..render.viz import SCENES, VIZ
from ..sources.spotify import Spotify


def viz_box(c: Ctx) -> tuple[int, int, int, int]:
    return c.left, 56, c.x1 - 18, 302


def render(c: Ctx) -> None:
    d, m = c.d, c.state.music
    left, _, right, _ = viz_box(c)
    d.text((left, 26), "SPOTIFY", font=theme.sans(18), fill=theme.DIM)
    badge = {"playing": "> playing", "paused": "|| paused"}.get(m.state, "")
    d.text((right, 29), badge, font=theme.mono(15), fill=theme.FAINT, anchor="ra")
    if m.state not in ("playing", "paused"):
        d.text((left, 310), "Spotify is off" if m.state == "off" else "nothing playing",
               font=theme.sans(20), fill=theme.FAINT)
        return
    title_font = theme.sans(20)
    d.text((left, 310), draw.clip(d, m.title, title_font, right - left), font=title_font,
           fill=theme.TEXT)
    pos = m.position(time.time())
    clock = f" · {draw.mmss(pos)} / {draw.mmss(m.duration_s)}"
    small = theme.mono(15)
    artist = draw.clip(d, m.artist, small, right - left - d.textlength(clock, font=small))
    d.text((left, 340), artist + clock, font=small, fill=theme.DIM)
    d.rounded_rectangle((left, 368, right, 372), radius=2, fill=theme.CARD)
    if m.duration_s:
        done = left + max(4, (right - left) * pos / m.duration_s)
        d.rounded_rectangle((left, 368, done, 372), radius=2, fill=theme.GOOD)


def paint(c: Ctx, now: float) -> None:
    scene = c.settings.get("scene", SCENES[0])
    VIZ.scene = SCENES.index(scene) if scene in SCENES else 0
    VIZ.draw(c.img, viz_box(c), c.state.music, now)


def on_tap(action: str) -> None:
    if action == "scene":
        from .. import deck
        now = deck.settings("spotify").get("scene", SCENES[0])
        nxt = SCENES[(SCENES.index(now) + 1) % len(SCENES) if now in SCENES else 0]
        deck.update_settings("spotify", {"scene": nxt})


register(Tile(
    "spotify", "Spotify", 370, render,
    sources=(Spotify,),
    fields=(Field("scene", "Visualizer", "select", SCENES),),
    defaults={"scene": SCENES[0]},
    taps=lambda c: {"scene": viz_box(c)},
    on_tap=on_tap,
    paint=paint,
    animated=VIZ.animated_state,
))
