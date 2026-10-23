"""Outside: clock, sunrise/sunset, weather and two price quotes for a city.

Tap the weather for a 10-day forecast. City and quotes are settings (see
sources/outside.py for where the numbers come from).
"""
from __future__ import annotations

from ..deck import Ctx, Field, Tile, register
from ..render import draw, icons, theme, views
from ..sources import outside
from ..state import DeckState, Quote
from ..sun import sun_times

SIGNS = {"EUR": "€", "USD": "$", "GBP": "£", "JPY": "¥", "CHF": "Fr", "PLN": "zł"}


def price(q: Quote) -> str | None:
    """Rates to 4 places, big prices whole, the rest to 2; decimal comma."""
    if q.price is None:
        return None
    if q.spec.startswith("fx:"):
        return f"{q.price:.4f}".replace(".", ",")
    text = f"{q.price:,.{0 if q.price >= 1000 else 2}f}"
    text = text.replace(",", " ").replace(".", ",")
    return f"{text} {SIGNS.get(q.currency, q.currency)}".strip()


def _quote_row(c: Ctx, y: int, q: Quote) -> None:
    d = c.d
    d.text((c.left, y + 6), q.label, font=theme.sans(16), fill=theme.DIM)
    shown = price(q)
    if shown is None:
        d.text((c.right, y), "—", font=theme.mono(24), fill=theme.FAINT, anchor="ra")
        return
    d.text((c.right, y), shown, font=theme.mono(24),
           fill=theme.STALE if q.stale else theme.TEXT, anchor="ra")
    up, down = q.change_pct > 0, q.change_pct < 0
    arrow = "▲" if up else "▼" if down else "·"
    color = theme.STALE if q.stale else theme.GOOD if up else theme.BAD if down else theme.FAINT
    d.text((c.right, y + 32), f"{arrow} {abs(q.change_pct):.2f}%", font=theme.mono(15),
           fill=color, anchor="ra")


def render(c: Ctx) -> None:
    d, s = c.d, c.state
    d.text((c.right, 26), f"{s.now:%H:%M}", font=theme.sans(46), fill=theme.TEXT, anchor="ra")
    d.text((c.right, 86), f"{s.now:%a %b %-d}", font=theme.sans(20), fill=theme.DIM, anchor="ra")

    rise, set_ = sun_times(s.now.date(), s.place.lat, s.place.lon)
    if rise and set_:
        d.text((c.left, 34), f"↑ {rise:%H:%M}", font=theme.mono(19), fill=theme.WARN)
        d.text((c.left, 62), f"↓ {set_:%H:%M}", font=theme.mono(19), fill=theme.DIM)
    d.text((c.left, 96), draw.clip(d, s.place.name, theme.sans(16), 170),
           font=theme.sans(16), fill=theme.FAINT)

    wx, y = s.weather, 126
    if wx.temp_c is None:
        d.text((c.left, y + 10), "—", font=theme.mono(22), fill=theme.FAINT)
    else:
        d.text((c.left, y), f"{wx.temp_c:.1f}°".replace(".", ","), font=theme.sans(56),
               fill=theme.STALE if wx.stale else theme.TEXT)
        if wx.high_c is not None and wx.low_c is not None:
            d.text((c.right, y + 6), f"▲ {wx.high_c:.0f}°", font=theme.mono(17),
                   fill=theme.DIM, anchor="ra")
            d.text((c.right, y + 32), f"▼ {wx.low_c:.0f}°", font=theme.mono(17),
                   fill=theme.FAINT, anchor="ra")
        extra = [f"{wx.humidity_pct:.0f}%" if wx.humidity_pct is not None else "",
                 f"{wx.pressure_hpa:.0f} hPa" if wx.pressure_hpa else "",
                 f"{wx.rain_mm:.1f} mm" if wx.rain_mm else ""]
        d.text((c.left, y + 70), "  ".join(x for x in extra if x), font=theme.mono(16),
               fill=theme.FAINT)

    for i, q in enumerate(s.quotes[: outside.MAX_QUOTES]):
        _quote_row(c, 232 + 66 * i, q)


def forecast(s: DeckState, d, size: tuple[int, int]) -> None:
    width, height = size
    pad = 28
    d.text((pad, 26), "10-DAY FORECAST", font=theme.sans(30), fill=theme.ACCENT)
    sub = f"{s.place.name} · open-meteo.com"
    if s.weather.temp_c is not None:
        sub = f"now {s.weather.temp_c:.1f}° · ".replace(".", ",") + sub
    d.text((pad + 300, 36), sub, font=theme.sans(18), fill=theme.DIM)
    days = s.forecast[:10]
    if not days:
        d.text((width // 2, height // 2), "forecast not loaded yet", font=theme.sans(26),
               fill=theme.FAINT, anchor="mm")
        return
    col = (width - 2 * pad) / len(days)
    lo, hi = min(x.low_c for x in days), max(x.high_c for x in days)
    span = max(hi - lo, 1.0)
    today = s.now.date()
    for i, day in enumerate(days):
        x0 = pad + i * col
        cx = x0 + col / 2
        is_today = day.day == today
        if is_today:
            d.rounded_rectangle((x0 + 6, 96, x0 + col - 6, height - 18), radius=14, fill=theme.CARD)
        d.text((cx, 110), "Today" if is_today else f"{day.day:%a}", font=theme.sans(24),
               fill=theme.TEXT if is_today else theme.DIM, anchor="ma")
        d.text((cx, 140), f"{day.day:%d.%m}", font=theme.mono(16), fill=theme.FAINT, anchor="ma")
        icons.weather_icon(d, cx, 212, 84, day.code)
        d.text((cx, 262), f"{day.high_c:.0f}°", font=theme.sans(40), fill=theme.TEXT, anchor="ma")
        d.text((cx, 310), f"{day.low_c:.0f}°", font=theme.mono(22), fill=theme.DIM, anchor="ma")
        # Every day's bar on one shared scale, so warm and cold days compare.
        bx0, bx1 = x0 + 26, x0 + col - 26
        d.rounded_rectangle((bx0, 344, bx1, 350), radius=3, fill=theme.LINE)
        a = bx0 + (bx1 - bx0) * (day.low_c - lo) / span
        b = bx0 + (bx1 - bx0) * (day.high_c - lo) / span
        d.rounded_rectangle((a, 344, max(b, a + 6), 350), radius=3, fill=theme.ACCENT)
        wet = day.rain_pct >= 50 or day.rain_mm >= 1
        tint = icons.RAIN if wet else theme.FAINT
        d.text((cx, 366), f"{day.rain_mm:.1f} mm" if day.rain_mm >= 0.1 else "dry",
               font=theme.mono(18), fill=tint, anchor="ma")
        d.text((cx, 392), f"{day.rain_pct:.0f}%", font=theme.mono(16), fill=tint, anchor="ma")
        d.text((cx, 418), f"{day.wind_kmh:.0f} km/h", font=theme.mono(15),
               fill=theme.WARN if day.wind_kmh >= 40 else theme.FAINT, anchor="ma")


views.register("forecast", forecast)
register(Tile(
    "outside", "Outside", 360, render,
    sources=(outside.CityWeather, outside.CityForecast, outside.Quotes),
    fields=(Field("city", "City — weather, sun, forecast", "city"),
            Field("quotes", "Quotes (up to two)", "quotes",
                  hint="fx:EUR/PLN · crypto:BTC/EUR · stock:NVDA")),
    defaults=outside.DEFAULTS,
    check=outside.check,
    taps=lambda c: {"open:forecast": (c.x0, 110, c.x1, 225)},
))
