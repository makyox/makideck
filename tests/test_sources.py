import json
from datetime import date, datetime, timedelta
from pathlib import Path

from makideck.sources import outside
from makideck.sources.ccusage import parse_daily
from makideck.sources.claude_limits import parse_usage
from makideck.sources.spotify import parse_player
from makideck.sources.transcripts import Transcripts, model_name, parse_turn, summarize
from makideck.store import Store

GIG_PAGE = """
<td>Temperatura</td><td>16,7&nbsp;&deg;C</td><td>62,1 &deg;F</td>
<td>Wilgotność</td><td>71 %</td>
<td>Ciśnienie zredukowane</td><td>1 010,8&nbsp;hPa</td>
<td>Dzisiejsze opady</td><td>0,2 mm</td>
<td>Najwyższa temperatura</td><td>Najniższa temperatura</td>
<td>20,3 °C o&nbsp;14:47</td><td>8,3 °C o&nbsp; 5:43</td>
"""


def test_gig_page():
    w = outside.parse_gig(GIG_PAGE)
    assert (w.temp_c, w.humidity_pct, w.pressure_hpa, w.rain_mm) == (16.7, 71, 1010.8, 0.2)
    assert (w.high_c, w.low_c) == (20.3, 8.3)


def test_open_meteo_current_and_days():
    w = outside.parse_current({"current": {"temperature_2m": 11.7, "relative_humidity_2m": 70,
                                           "pressure_msl": 1017.4},
                               "daily": {"temperature_2m_max": [14.0], "temperature_2m_min": [6.5],
                                         "precipitation_sum": [0.0]}})
    assert (w.temp_c, w.high_c, w.low_c) == (11.7, 14.0, 6.5)
    days = outside.parse_days({"daily": {"time": ["2026-10-23", "2026-10-24"], "weather_code": [3, None],
                                         "temperature_2m_max": [14, 12], "temperature_2m_min": [6, 5]}})
    assert days[0].day == date(2026, 10, 23) and days[1].code == 0 and days[1].rain_mm == 0


def test_quote_specs_and_cities():
    assert outside.normalize(" fx:eur/pln ") == "fx:EUR/PLN"
    assert outside.normalize("stock:^gspc") == "stock:^GSPC"
    assert outside.normalize("EUR/PLN") is None
    assert outside.provider("fx:USD/PLN") == "nbp" and outside.provider("fx:EUR/USD") == "yahoo"
    assert outside.provider("crypto:BTC/EUR") == "kraken"
    kato = outside.as_city({"name": "Katowice", "latitude": 50.258, "longitude": 19.027,
                            "admin1": "Śląskie", "country": "Polska"})
    assert kato["station"] == "gig" and kato["region"] == "Śląskie, Polska"
    assert outside.as_city({"name": "Kraków", "latitude": 50.06, "longitude": 19.94})["station"] == ""


def test_outside_check_without_network():
    clean, errors = outside.check({"city": {"name": "X"}, "quotes": ["junk", ""]})
    assert len(errors) == 2 and clean["quotes"] == []


def test_usage_and_spend():
    lim = parse_usage({"five_hour": {"utilization": 12.0, "resets_at": "2026-10-23T18:00:00+00:00"},
                       "seven_day": None})
    assert lim.session.pct == 12 and lim.session.resets_at is not None and lim.week is None
    spend = parse_daily({"daily": [
        {"period": "2026-10-22", "totalTokens": 100, "totalCost": 1.5},
        {"period": "2026-10-23", "totalTokens": 50, "totalCost": 0.5, "inputTokens": 10,
         "outputTokens": 5, "cacheReadTokens": 30, "cacheCreationTokens": 5}]}, date(2026, 10, 23))
    assert (spend.week_tokens, spend.week_usd, spend.today_tokens, spend.cache_tokens) == (150, 2.0, 50, 35)


def test_spotify_player():
    m = parse_player("playing\tSong\tArtist\t95,5\t308000\tspotify:track:x\n", 100.0)
    assert (m.state, m.title, m.position_s, m.duration_s) == ("playing", "Song", 95.5, 308.0)
    assert m.position(102.0) == 97.5
    assert parse_player("off\n", 0).state == "off" and parse_player("stopped", 0).state == "stopped"


def _line(at: datetime, tokens: int, model: str = "claude-opus-5-5-20260101", cwd: str = "/x/proj") -> bytes:
    return json.dumps({"type": "assistant", "timestamp": at.isoformat(), "cwd": cwd,
                       "message": {"model": model, "usage": {"input_tokens": tokens}}}).encode()


def test_transcripts_summary():
    now = datetime.now().astimezone().replace(hour=15, minute=0)
    s = Path("/t/a.jsonl")
    turns = [parse_turn(_line(now - timedelta(minutes=1), 600), s),
             parse_turn(_line(now - timedelta(hours=2), 400, "claude-haiku-4-5", "/x/other"), Path("/t/b.jsonl"))]
    assert parse_turn(b'{"type":"user"}', s) is None and parse_turn(b"not json", s) is None
    w = summarize(turns, now)
    assert w.active and w.project == "proj" and w.model == "Opus 5.5"
    assert w.live_sessions == 1 and w.sessions_today == 2
    assert w.hourly[15 - 1] == 600 or w.hourly[14] == 600
    assert w.by_project == [("proj", 600), ("other", 400)]
    assert w.tokens_per_min == 60
    assert model_name("claude-weird-9") == "weird-9"


def test_transcripts_read_only_new_complete_lines(tmp_path):
    now = datetime.now().astimezone()
    f = tmp_path / "proj" / "s.jsonl"
    f.parent.mkdir()
    f.write_bytes(_line(now, 10) + b"\n" + _line(now, 20)[:30])       # second line half-written
    src = Transcripts(Store(), root=tmp_path)
    src.poll()
    assert src.store.snapshot().work.sessions_today == 1
    assert sum(src.store.snapshot().work.hourly) == 10
    with f.open("ab") as fh:
        fh.write(_line(now, 20)[30:] + b"\n")
    src.poll()
    assert sum(src.store.snapshot().work.hourly) == 30
