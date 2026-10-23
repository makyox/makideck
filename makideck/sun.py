"""Sunrise/sunset from coordinates — NOAA's simplified solar position formulas.

Accurate to about a minute at mid latitudes, which is all a desk clock needs.
No network involved.
"""
from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta

_ZENITH = 90.833  # sun centre below horizon incl. refraction + disc radius


def sun_times(day: date, lat: float, lon: float
              ) -> tuple[datetime | None, datetime | None]:
    """(sunrise, sunset) as naive local datetimes; None during polar day/night."""
    gamma = 2 * math.pi / 365 * (day.timetuple().tm_yday - 1)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma)
                       - 0.032077 * math.sin(gamma)
                       - 0.014615 * math.cos(2 * gamma)
                       - 0.040849 * math.sin(2 * gamma))
    decl = (0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma)
            - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma)
            - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma))
    phi = math.radians(lat)
    cos_ha = (math.cos(math.radians(_ZENITH)) / (math.cos(phi) * math.cos(decl))
              - math.tan(phi) * math.tan(decl))
    if not -1 <= cos_ha <= 1:
        return None, None
    ha = math.degrees(math.acos(cos_ha))
    midnight_utc = datetime(day.year, day.month, day.day, tzinfo=UTC)

    def at(minutes: float) -> datetime:
        return (midnight_utc + timedelta(minutes=minutes)
                ).astimezone().replace(tzinfo=None)

    return (at(720 - 4 * (lon + ha) - eqtime),
            at(720 - 4 * (lon - ha) - eqtime))
