"""DeckState: everything tiles draw from, filled in by sources.

Sources replace whole sections (never mutate one in place), so a snapshot is
a cheap shallow copy. A section a source couldn't refresh keeps its last
value with `stale=True`; tiles grey it out instead of going blank.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta


@dataclass
class Limit:
    """One Claude usage window: the 5-hour session or the week."""
    pct: float
    resets_at: datetime | None = None


@dataclass
class Limits:
    session: Limit | None = None
    week: Limit | None = None
    stale: bool = False


@dataclass
class Spend:
    """Tokens and what they'd cost at API prices (ccusage)."""
    today_usd: float = 0.0
    today_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_tokens: int = 0
    week_usd: float = 0.0
    week_tokens: int = 0
    stale: bool = False


@dataclass
class Work:
    """What Claude Code is doing, from today's session transcripts."""
    project: str = ""
    model: str = ""
    active: bool = False
    last_at: datetime | None = None
    tokens_per_min: float = 0.0
    live_sessions: int = 0
    sessions_today: int = 0
    hourly: list[int] = field(default_factory=list)          # since midnight
    by_project: list[tuple[str, int]] = field(default_factory=list)
    by_model: list[tuple[str, int]] = field(default_factory=list)
    stale: bool = False


@dataclass
class Place:
    """Where weather, sun times and the forecast are for."""
    name: str = "Warszawa"
    lat: float = 52.2298
    lon: float = 21.0118
    station: str = ""          # "gig" = the GIG station in Katowice


@dataclass
class Weather:
    temp_c: float | None = None
    high_c: float | None = None
    low_c: float | None = None
    humidity_pct: float | None = None
    pressure_hpa: float | None = None
    rain_mm: float | None = None
    stale: bool = False


@dataclass
class Day:
    """One day of the forecast; code is the WMO weather code."""
    day: date
    code: int
    high_c: float
    low_c: float
    rain_mm: float = 0.0
    rain_pct: float = 0.0
    wind_kmh: float = 0.0


@dataclass
class Quote:
    """A price row: spec "fx:EUR/PLN", "crypto:BTC/EUR" or "stock:NVDA"."""
    spec: str
    label: str
    price: float | None = None
    currency: str = ""
    change_pct: float = 0.0
    stale: bool = False


@dataclass
class Music:
    """The Spotify desktop app's player."""
    state: str = "off"          # off | stopped | paused | playing
    title: str = ""
    artist: str = ""
    position_s: float = 0.0
    duration_s: float = 0.0
    track_id: str = ""
    polled_at: float = 0.0      # time.time() when position_s was read

    def position(self, now: float) -> float:
        """Where playback is now, running on from the last poll."""
        pos = self.position_s + (max(0.0, now - self.polled_at)
                                 if self.state == "playing" else 0.0)
        return min(pos, self.duration_s) if self.duration_s else pos


@dataclass
class DeckState:
    now: datetime = field(default_factory=datetime.now)
    limits: Limits = field(default_factory=Limits)
    spend: Spend = field(default_factory=Spend)
    work: Work = field(default_factory=Work)
    place: Place = field(default_factory=Place)
    weather: Weather = field(default_factory=Weather)
    forecast: list[Day] = field(default_factory=list)
    quotes: list[Quote] = field(default_factory=list)
    music: Music = field(default_factory=Music)


def demo_state(now: datetime | None = None) -> DeckState:
    """Plausible made-up data: previews, screenshots, `run --demo`, tests."""
    now = now or datetime.now()
    hours = [0, 0, 0, 0, 0, 0, 0, 3, 11, 16, 9, 4, 13, 21, 25, 12, 7,
             18, 23, 15, 6, 2, 0, 0]
    return DeckState(
        now=now,
        limits=Limits(Limit(23.0, now + timedelta(hours=2, minutes=41)),
                      Limit(41.0, now + timedelta(days=3, hours=6))),
        spend=Spend(today_usd=18.42, today_tokens=31_400_000, input_tokens=21_900,
                    output_tokens=212_000, cache_tokens=31_166_000,
                    week_usd=163.0, week_tokens=274_000_000),
        work=Work(project="makideck", model="Opus 5.5", active=True,
                  last_at=now - timedelta(seconds=6), tokens_per_min=1_180_000,
                  live_sessions=2, sessions_today=6,
                  hourly=[h * 1_000_000 for h in hours[: now.hour + 1]],
                  by_project=[("makideck", 14_200_000), ("pixel-garden", 8_900_000),
                              ("dotfiles", 4_100_000), ("blog", 2_600_000),
                              ("notes", 1_600_000)],
                  by_model=[("Opus 5.5", 24_100_000), ("Sonnet 5.5", 6_000_000),
                            ("Haiku 5.5", 1_300_000)]),
        place=Place(),
        weather=Weather(temp_c=14.2, high_c=17.0, low_c=7.0, humidity_pct=68,
                        pressure_hpa=1016.0, rain_mm=0.4),
        forecast=[Day(now.date() + timedelta(days=i), code, hi, lo, mm, pp, wind)
                  for i, (code, hi, lo, mm, pp, wind) in enumerate([
                      (2, 17.0, 7.0, 0.4, 20, 14), (61, 12.5, 6.1, 6.2, 85, 22),
                      (3, 13.8, 5.0, 0.0, 15, 12), (0, 15.2, 3.9, 0.0, 5, 9),
                      (1, 16.0, 6.4, 0.0, 10, 11), (80, 11.9, 6.8, 4.1, 70, 27),
                      (45, 10.4, 4.2, 0.1, 25, 6), (71, 3.1, -1.8, 2.4, 65, 19),
                      (95, 9.6, 4.0, 11.0, 90, 44), (2, 12.3, 3.3, 0.0, 10, 13)])],
        quotes=[Quote("fx:EUR/PLN", "EUR/PLN", 4.2716, "PLN", 0.12),
                Quote("crypto:BTC/EUR", "BTC/EUR", 71_240.0, "EUR", -1.38)],
        music=Music(state="playing", title="Synthetic Sunrise", artist="The Pixel Choir",
                    position_s=84.0, duration_s=262.0, track_id="demo:track",
                    polled_at=now.timestamp()),
    )
