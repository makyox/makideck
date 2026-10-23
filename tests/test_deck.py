from makideck import deck
from makideck.deck import Ctx, Field, Tile


def test_default_columns_fill_the_panel():
    cols = deck.columns(1920)
    assert [t.id for t, _, _ in cols] == ["claude", "spotify", "projects", "session", "outside"]
    assert cols[0][1] == 0 and cols[-1][2] == 1920
    assert all(a[2] == b[1] for a, b in zip(cols, cols[1:], strict=False))


def test_hiding_a_tile_stretches_the_rest():
    assert deck.set_order(["claude", "outside"])
    assert sorted(deck.hidden()) == ["projects", "session", "spotify"]
    (_, a0, a1), (_, b0, b1) = deck.columns(1920)
    assert (a0, b1) == (0, 1920)
    assert abs((a1 - a0) / (b1 - b0) - 460 / 360) < 0.01


def test_bad_orders_are_refused():
    assert not deck.set_order([])
    assert not deck.set_order(["claude", "claude"])
    assert not deck.set_order(["claude", "nope"])


def test_settings_merge_defaults_and_persist(tmp_path):
    saved, errors = deck.update_settings("projects", {"rows": "3"})
    assert not errors and saved["rows"] == "3"
    deck.set_order(["projects", "claude"])
    deck.save(tmp_path / "deck.json")
    deck._settings.clear()
    deck.reset_order()
    assert deck.settings("projects")["rows"] == "5"
    deck.load(tmp_path / "deck.json")
    assert deck.settings("projects")["rows"] == "3"
    assert deck.order() == ["projects", "claude"]


def test_check_rejects_bad_settings_and_keeps_the_old_ones():
    _, errors = deck.update_settings("outside", {"quotes": ["not-a-spec"]})
    assert errors and deck.settings("outside")["quotes"] == ["fx:EUR/PLN", "crypto:BTC/EUR"]


def test_listeners_hear_changes():
    heard = []
    deck.on_change(heard.append)
    deck.update_settings("projects", {"rows": "4"})
    deck.set_order(["claude"])
    assert heard == ["projects", "*"]


def test_a_new_tile_module():
    seen = {}

    def draw(c: Ctx) -> None:
        seen["box"] = (c.x0, c.x1, c.bottom, c.settings["greeting"])
    deck.register(Tile("hello", "Hello", 300, draw,
                       fields=(Field("greeting", "Greeting"),), defaults={"greeting": "hi"}))
    try:
        assert "hello" in deck.hidden()
        deck.set_order([*deck.order(), "hello"])
        from makideck.render import dashboard
        from makideck.state import demo_state
        dashboard.dashboard(demo_state())
        x0, x1, bottom, greeting = seen["box"]
        assert x1 == 1920 and bottom == 462 - dashboard.FOOTER and greeting == "hi"
        assert {"key": "greeting", "label": "Greeting", "kind": "text", "options": (), "hint": ""} in \
            next(t["fields"] for t in deck.to_json()["tiles"] if t["id"] == "hello")
    finally:
        del deck.REGISTRY["hello"]


def test_the_example_plugin_loads_and_draws():
    from pathlib import Path

    from makideck.render import dashboard
    from makideck.state import demo_state
    deck.load_tiles(Path(__file__).parent.parent / "examples")
    try:
        assert "countdown" in deck.hidden()
        _, errors = deck.update_settings("countdown", {"date": "soon"})
        assert errors
        deck.set_order(["claude", "countdown"])
        assert dashboard.frame(demo_state()).getbbox() is not None
    finally:
        deck.REGISTRY.pop("countdown", None)


def test_user_modules_can_use_dataclasses(tmp_path):
    (tmp_path / "dc.py").write_text(
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "from makideck.deck import Tile, register\n"
        "@dataclass\nclass Reading:\n    value: float = 0.0\n"
        "register(Tile('dc', 'Dataclass', 200, lambda c: None))\n")
    deck.load_tiles(tmp_path)
    try:
        assert "dc" in deck.REGISTRY
    finally:
        deck.REGISTRY.pop("dc", None)
