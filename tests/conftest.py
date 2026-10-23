import pytest

from makideck import deck


@pytest.fixture(autouse=True)
def fresh_deck(tmp_path, monkeypatch):
    """Built-in tiles in default order, no saved settings, nothing on disk."""
    monkeypatch.setattr(deck, "DECK_FILE", tmp_path / "deck.json")
    deck.load_tiles(tmp_path / "no-plugins")      # imports are cached; cheap
    deck.reset_order()
    deck._settings.clear()
    deck._listeners.clear()
    yield
    deck._settings.clear()
    deck._listeners.clear()
    deck.reset_order()
