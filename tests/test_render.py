import time

from PIL import Image

from makideck import deck
from makideck.render import dashboard, draw
from makideck.render.viz import AsciiViz
from makideck.state import Quote, demo_state
from makideck.tiles.outside import price
from makideck.ui import Controls


def test_dashboard_and_forecast_render():
    s = demo_state()
    for size in (dashboard.SIZE, (1280, 480)):
        img = dashboard.frame(s, size)
        assert img.size == size and img.getbbox() is not None
    assert dashboard.frame(s, view="forecast").getbbox() is not None


def test_empty_state_renders():
    from makideck.state import DeckState
    assert dashboard.frame(DeckState()).size == dashboard.SIZE


def test_a_crashing_tile_does_not_take_the_panel_down():
    original = deck.REGISTRY["session"]
    deck.REGISTRY["session"] = deck.Tile("session", "Session", 330, lambda c: 1 / 0)
    try:
        assert dashboard.frame(demo_state()).getbbox() is not None
    finally:
        deck.REGISTRY["session"] = original


def test_taps_follow_the_tiles():
    s = demo_state()
    zones = {z["action"]: z for z in dashboard.tap_zones(s, dashboard.SIZE, None)}
    assert set(zones) == {"scene", "open:forecast"}
    deck.set_order(["outside", "claude"])
    zone = dashboard.hit(s, dashboard.SIZE, None, 100, 150)
    assert zone["action"] == "open:forecast"


def test_controls_tap_scene_and_views():
    ui, s = Controls(persist=False), demo_state()
    x0, y0, x1, y1 = next(z["box"] for z in dashboard.tap_zones(s, dashboard.SIZE, None)
                          if z["action"] == "scene")
    assert ui.tap(s, dashboard.SIZE, (x0 + x1) // 2, (y0 + y1) // 2) == "scene"
    assert deck.settings("spotify")["scene"] == "stars"
    assert ui.tap(s, dashboard.SIZE, 1700, 150) == "open:forecast"
    assert ui.view == "forecast"
    assert ui.tap(s, dashboard.SIZE, 1840, 52) == "close" and ui.view is None


def test_visualizer_is_fast_enough():
    viz, music = AsciiViz(), demo_state().music
    img = Image.new("RGB", dashboard.SIZE)
    for scene in (0, 1):
        viz.scene = scene
        t0 = time.perf_counter()
        for i in range(10):
            viz.draw(img, (516, 56, 812, 302), music, 1000 + i / 15)
        assert (time.perf_counter() - t0) / 10 < 0.05


def test_formatting():
    assert draw.tokens(999) == "999" and draw.tokens(1234) == "1.2k" and draw.tokens(27_100_000) == "27.1M"
    assert draw.until(7 * 60) == "7m" and draw.until(2 * 3600 + 240) == "2h 04m"
    assert draw.until(5 * 86400 + 18 * 3600) == "5d 18h"
    assert draw.mmss(84) == "1:24"
    assert price(Quote("fx:EUR/PLN", "EUR/PLN", 4.36412, "PLN")) == "4,3641"
    assert price(Quote("crypto:BTC/EUR", "BTC/EUR", 75399.4, "EUR")) == "75 399 €"
    assert price(Quote("stock:NVDA", "NVDA", 212.0, "USD")) == "212,00 $"
    assert price(Quote("stock:CDR.WA", "CDR.WA", 245.5, "PLN")) == "245,50 zł"
    assert price(Quote("stock:X", "X")) is None


def test_clip():
    from PIL import ImageDraw

    from makideck.render import theme
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    f = theme.mono(16)
    assert draw.clip(d, "short", f, 500) == "short"
    cut = draw.clip(d, "a fairly long project name", f, 80)
    assert cut.endswith("…") and d.textlength(cut, font=f) <= 80
