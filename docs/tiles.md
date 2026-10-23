# Writing a tile

A tile is a column of the panel above the footer. You write one Python file
that calls `register(Tile(...))`. Put it in `~/.config/makideck/tiles/` and
restart makideck (menu bar → Restart). The tile shows up under *Hidden tiles*
in the editor, where you can add it.

```python
from makideck.deck import Ctx, Field, Tile, register

register(Tile(
    id="pomodoro",          # stable key: settings and the layout are saved under it
    name="Pomodoro",        # shown in the editor
    width=300,              # natural width; visible tiles are stretched to fill the panel
    draw=render,            # draws the tile, see below
    # all optional:
    sources=(),             # data sources it needs (store.Source subclasses)
    fields=(),              # settings form, see below
    defaults={},            # default settings
    check=None,             # validate settings before they're saved
    taps=None,              # clickable zones in the live view
    on_tap=None,            # what your own tap actions do
    paint=None,             # a live layer repainted every frame
    animated=None,          # when the deck should run at the high frame rate
))
```

## Drawing

`draw(c: Ctx)` gets a Pillow `ImageDraw` (`c.d`) for the whole panel, so stay
inside your column:

| | |
| --- | --- |
| `c.x0`, `c.x1` | the column's edges in panel pixels |
| `c.left`, `c.right` | the same, minus the 28 px padding: where text goes |
| `c.top`, `c.bottom` | 0 and the footer line (388 on the 9.16") |
| `c.state` | everything sources know: `DeckState` in [state.py](../makideck/state.py) |
| `c.settings` | this tile's settings (defaults + what the user saved) |
| `c.img` | the image, for pasting bitmaps |

`makideck.render.theme` has the palette (`TEXT`, `DIM`, `FAINT`, `ACCENT`,
`GOOD`, `WARN`, `BAD`…) and the fonts (`theme.sans(size)`, `theme.mono(size)`).
`makideck.render.draw` has helpers: `meter`, `bars`, `split_bar`, `clip`
(ellipsis), `shrink` (fit a font to a width), `tokens` (27.1M), `until`
(2h 04m).

The built-in tiles use these conventions: a small caps header at y=26 in
`sans(18)` and `DIM`, the main number big, details in `mono` and `FAINT`, and
`STALE` grey for data that couldn't be refreshed. Look at
[tiles/session.py](../makideck/tiles/session.py) for a short one.

If `draw` raises, the tile shows the error in red and the rest of the panel
carries on.

## Settings

`fields` builds the tile's form in the editor:

```python
fields=(Field("label", "Label"),
        Field("units", "Units", "select", ("metric", "imperial")),
        Field("seconds", "Show seconds", "toggle"),
        Field("goal", "Daily goal", "number", hint="tokens")),
defaults={"label": "Focus", "units": "metric", "seconds": False, "goal": 1000000},
```

The kinds are `text`, `number`, `select` (with `options`) and `toggle`. There
are also the special `city` and `quotes` pickers that the Outside tile uses.
`check(values) -> (clean, errors)` runs when the user clicks Save. Return
error strings to refuse the change. The editor shows them, and nothing is
saved.

## Data

Don't fetch anything inside `draw`: it runs on every frame. Write a
`Source` instead. It polls on its own thread and stores what it finds in
the shared state:

```python
from makideck.store import Source

class Pomodoros(Source):
    every = 30.0                  # seconds between polls
    sections = ()                 # DeckState fields to mark stale when poll() fails

    def poll(self) -> None:
        self.store.set(...)       # replace whole sections, don't mutate them
```

List it in `sources=(Pomodoros,)`. makideck starts each source once, when
the first tile that needs it goes on the panel. To keep your own data, either add
a field to `DeckState`, or keep it in your module and read it in `draw`. Call
`self.poke()` from a `deck.on_change` listener to refresh as soon as your
settings change (see [sources/outside.py](../makideck/sources/outside.py)).

## Taps, views and animation

- `taps(c)` returns `{action: (x0, y0, x1, y1)}`. The live view highlights
  these zones. `"open:<view>"` opens a full-screen view registered with
  `makideck.render.views.register(name, fn)`. Any other action goes to your
  `on_tap(action)`.
- `paint(c, now)` draws a layer that changes every frame, like the Spotify
  visualizer. The dashboard is cached, and only `paint` runs between full
  redraws. Return `True` from `animated(state)` while it's worth running at
  `live_fps` (15 by default) instead of `fps` (2).

## Try it without the panel

```bash
uv run makideck run --demo --no-panel
```

Demo data, no USB. Open <http://127.0.0.1:8787/editor>, find your tile in the
tray and add it.
