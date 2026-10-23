"""Weather, forecast and price quotes for the outside tile.

Which city and which quotes come from the tile's settings:

    {"city": {"name", "lat", "lon", "station", "region"},
     "quotes": ["fx:EUR/PLN", "crypto:BTC/EUR"]}

Weather is Open-Meteo's current conditions for the city — or, within 15 km
of Katowice, the GIG station's own page (a real thermometer). The 10-day
forecast is Open-Meteo too. Quotes by spec:

    fx:EUR/PLN      NBP mid rate for anything quoted in PLN, Yahoo otherwise
    crypto:BTC/EUR  Kraken ticker, change since today's open
    stock:NVDA      Yahoo Finance, change since the previous close

No API keys anywhere.
"""
from __future__ import annotations

import html
import json
import math
import re
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, replace
from datetime import date

from .. import deck
from ..state import Day, Place, Quote, Weather
from ..store import Source

TILE = "outside"
AGENT = "Mozilla/5.0 (makideck)"
GIG = Place("Katowice", 50.2716, 19.0252, "gig")
DEFAULTS = {"city": {**asdict(Place()), "region": "Mazowieckie, Polska"},
            "quotes": ["fx:EUR/PLN", "crypto:BTC/EUR"]}
MAX_QUOTES = 2


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def place() -> Place:
    c = deck.settings(TILE).get("city") or {}
    try:
        return Place(str(c["name"]), float(c["lat"]), float(c["lon"]), str(c.get("station", "")))
    except (KeyError, TypeError, ValueError):
        return Place()


# ── Cities ──────────────────────────────────────────────────────────────

def km_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    (la1, lo1), (la2, lo2) = (map(math.radians, a)), (map(math.radians, b))
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


def as_city(hit: dict) -> dict:
    lat, lon = float(hit["latitude"]), float(hit["longitude"])
    return {"name": hit["name"], "lat": lat, "lon": lon,
            "station": "gig" if km_between((lat, lon), (GIG.lat, GIG.lon)) < 15 else "",
            "region": ", ".join(x for x in (hit.get("admin1"), hit.get("country")) if x)}


def find_cities(query: str, lang: str = "en") -> list[dict]:
    q = urllib.parse.urlencode({"name": query, "count": 6, "language": lang})
    data = json.loads(fetch(f"https://geocoding-api.open-meteo.com/v1/search?{q}"))
    return [as_city(h) for h in data.get("results", [])]


# ── Weather ─────────────────────────────────────────────────────────────

def _pl_number(s: str) -> float:
    return float(re.sub(r"[\s\xa0]", "", s).replace(",", "."))


_N = r"(-?[\d\s\xa0]*\d(?:,\d+)?)"


def parse_gig(page: str) -> Weather:
    """Current conditions from meteo.gig.eu (Polish labels, decimal commas)."""
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())

    def find(label: str, unit: str) -> float | None:
        m = re.search(f"{label} {_N} ?{unit}", text)
        return _pl_number(m.group(1)) if m else None

    temp = find("Temperatura", "°C")
    if temp is None:
        raise ValueError("no temperature on the GIG page")
    extremes = re.search(f"Najniższa temperatura {_N} ?°C o [\\d: ]+ {_N} ?°C", text)
    return Weather(temp_c=temp,
                   high_c=_pl_number(extremes.group(1)) if extremes else None,
                   low_c=_pl_number(extremes.group(2)) if extremes else None,
                   humidity_pct=find("Wilgotność", "%"),
                   pressure_hpa=find("Ciśnienie zredukowane", "hPa"),
                   rain_mm=find("Dzisiejsze opady", "mm"))


def open_meteo(p: Place, **query: str) -> dict:
    q = urllib.parse.urlencode({"latitude": p.lat, "longitude": p.lon,
                                "timezone": "auto", **query})
    return json.loads(fetch(f"https://api.open-meteo.com/v1/forecast?{q}"))


def parse_current(data: dict) -> Weather:
    now, today = data["current"], data.get("daily") or {}

    def first(key: str) -> float | None:
        v = (today.get(key) or [None])[0]
        return None if v is None else float(v)
    return Weather(temp_c=float(now["temperature_2m"]),
                   humidity_pct=now.get("relative_humidity_2m"),
                   pressure_hpa=now.get("pressure_msl"),
                   high_c=first("temperature_2m_max"), low_c=first("temperature_2m_min"),
                   rain_mm=first("precipitation_sum"))


def parse_days(data: dict) -> list[Day]:
    daily = data["daily"]

    def col(key: str, i: int) -> float:
        v = (daily.get(key) or [])[i:i + 1]
        return float(v[0]) if v and v[0] is not None else 0.0
    return [Day(date.fromisoformat(d), int(col("weather_code", i)),
                col("temperature_2m_max", i), col("temperature_2m_min", i),
                col("precipitation_sum", i), col("precipitation_probability_max", i),
                col("wind_speed_10m_max", i))
            for i, d in enumerate(daily["time"])]


class _FollowsSettings(Source):
    def __init__(self, store) -> None:
        super().__init__(store)
        deck.on_change(lambda tid: tid == TILE and self.poke())


class CityWeather(_FollowsSettings):
    every = 300.0
    sections = ("weather",)

    def poll(self) -> None:
        p = place()
        self.store.set(place=p)
        if p.station == "gig":
            weather = parse_gig(fetch("https://meteo.gig.eu/"))
        else:
            weather = parse_current(open_meteo(
                p, forecast_days="1",
                current="temperature_2m,relative_humidity_2m,pressure_msl",
                daily="temperature_2m_max,temperature_2m_min,precipitation_sum"))
        self.store.set(weather=weather)


class CityForecast(_FollowsSettings):
    every = 1800.0

    def poll(self) -> None:
        self.store.set(forecast=parse_days(open_meteo(
            place(), forecast_days="10",
            daily="weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
                  "precipitation_probability_max,wind_speed_10m_max")))


# ── Quotes ──────────────────────────────────────────────────────────────

_SPEC = re.compile(r"(fx|crypto):[A-Z0-9]{2,10}/[A-Z]{3,4}|stock:[A-Z0-9.^=-]{1,15}")
_EVERY = {"nbp": 1800.0, "kraken": 60.0, "yahoo": 120.0}


def normalize(spec: str) -> str | None:
    kind, _, symbol = spec.strip().partition(":")
    spec = f"{kind.lower()}:{symbol.upper()}"
    return spec if _SPEC.fullmatch(spec) else None


def provider(spec: str) -> str:
    kind, _, symbol = spec.partition(":")
    if kind == "crypto":
        return "kraken"
    return "nbp" if kind == "fx" and symbol.endswith("/PLN") else "yahoo"


def get_quote(spec: str) -> Quote:
    kind, _, symbol = spec.partition(":")
    base, _, quote_ccy = symbol.partition("/")
    via = provider(spec)
    if via == "nbp":
        url = f"https://api.nbp.pl/api/exchangerates/rates/a/{base.lower()}/last/2/?format=json"
        fixings = [r["mid"] for r in json.loads(fetch(url))["rates"]]
        return Quote(spec, symbol, fixings[-1], "PLN", 100 * (fixings[-1] / fixings[0] - 1))
    if via == "kraken":
        pair = ("XBT" if base == "BTC" else base) + quote_ccy
        data = json.loads(fetch(f"https://api.kraken.com/0/public/Ticker?pair={pair}"))
        if data.get("error"):
            raise ValueError(", ".join(data["error"]))
        ticker = next(iter(data["result"].values()))
        last, opened = float(ticker["c"][0]), float(ticker["o"])
        return Quote(spec, symbol, last, quote_ccy, 100 * (last / opened - 1))
    yahoo = f"{base}{quote_ccy}=X" if kind == "fx" else symbol
    data = json.loads(fetch("https://query1.finance.yahoo.com/v8/finance/chart/"
                            f"{urllib.parse.quote(yahoo)}?range=5d&interval=1d"))
    found = (data.get("chart") or {}).get("result")
    if not found:
        raise ValueError(f"unknown symbol {yahoo}")
    meta = found[0]["meta"]
    price = float(meta["regularMarketPrice"])
    prev = float(meta.get("chartPreviousClose") or price)
    return Quote(spec, symbol, price, quote_ccy or meta.get("currency", ""),
                 100 * (price / prev - 1))


class Quotes(_FollowsSettings):
    """Ticks every 30 s; each provider has its own pace (NBP fixes daily)."""
    every = 30.0

    def __init__(self, store) -> None:
        super().__init__(store)
        self._have: dict[str, tuple[float, Quote]] = {}

    def poll(self) -> None:
        wanted = [s for s in map(normalize, deck.settings(TILE).get("quotes", [])) if s]
        now, rows, errors = time.time(), [], []
        for spec in wanted[:MAX_QUOTES]:
            at, q = self._have.get(spec, (0.0, None))
            if q is None or q.stale or now - at >= _EVERY[provider(spec)]:
                try:
                    q, at = get_quote(spec), now
                except Exception as e:
                    errors.append(f"{spec}: {e}")
                    q = replace(q, stale=True) if q else Quote(spec, spec.partition(":")[2], stale=True)
                self._have[spec] = (at, q)
            rows.append(q)
        self.store.set(quotes=rows)
        if errors:
            raise RuntimeError("; ".join(errors))


# ── Settings check (the editor's Save) ──────────────────────────────────

def check(values: dict) -> tuple[dict, list[str]]:
    clean, errors = {}, []
    if "city" in values:
        c = values.get("city") or {}
        try:
            clean["city"] = {"name": str(c["name"])[:40], "lat": float(c["lat"]),
                             "lon": float(c["lon"]), "station": str(c.get("station", "")),
                             "region": str(c.get("region", ""))[:80]}
        except (KeyError, TypeError, ValueError):
            errors.append("city: pick one from the search results")
    if "quotes" in values:
        have = deck.settings(TILE).get("quotes", [])
        clean["quotes"] = []
        for raw in [str(x) for x in values.get("quotes") or [] if str(x).strip()][:MAX_QUOTES]:
            spec = normalize(raw)
            if spec is None:
                errors.append(f"{raw}: use fx:EUR/PLN, crypto:BTC/EUR or stock:NVDA")
                continue
            if spec not in have:          # a new symbol: make sure it exists
                try:
                    get_quote(spec)
                except Exception as e:
                    errors.append(f"{spec}: {e}")
                    continue
            clean["quotes"].append(spec)
    return clean, errors
