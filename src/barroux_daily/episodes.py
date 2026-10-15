from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from .api import fetch_day
from .liturgy import Index

HOURS = ("lauds", "prime", "terce", "sext", "none", "vespers", "compline")
HOUR_LABELS = {
    "lauds": "Lauds",
    "prime": "Prime",
    "terce": "Terce",
    "sext": "Sext",
    "none": "Nones",
    "vespers": "Vespers",
    "compline": "Compline",
}
FIRST_YEAR = 2017


@dataclass(frozen=True)
class Episode:
    day: date  # the day this episode is published for
    hour: str
    recorded: date  # when the monks recorded it
    url: str
    celebration: str | None  # ordo name for `day`; None when matched by calendar date only


def candidate_dates(day: date, index: Index | None, first_year: int = FIRST_YEAR) -> list[date]:
    """Dates whose recordings could stand in for `day`, newest first."""
    cel = index.celebration(day) if index is not None else None
    if cel is not None:
        return [d for d in index.dates_for(cel.key) if d <= day and d.year >= first_year]
    dates = []
    for year in range(day.year, first_year - 1, -1):
        try:
            dates.append(date(year, day.month, day.day))
        except ValueError:  # Feb 29 in a non-leap year
            pass
    return dates


def episodes_for(
    day: date,
    get_day: Callable[[date], dict[str, str]] = fetch_day,
    index: Index | None = None,
    first_year: int = FIRST_YEAR,
) -> list[Episode]:
    cel = index.celebration(day) if index is not None else None
    name = cel.name if cel is not None else None
    found: dict[str, Episode] = {}
    for source in candidate_dates(day, index, first_year):
        if len(found) == len(HOURS):
            break
        for hour, url in get_day(source).items():
            if hour in HOURS and hour not in found:
                found[hour] = Episode(day, hour, source, url, name)
    return [found[h] for h in HOURS if h in found]
