from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
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
    same_feast: bool | None = None  # recording is of the same celebration; None if unknown
    source_celebration: str | None = None  # ordo name for `recorded`


# Under the 1963 monastic rubrics these hours always take their psalms from the weekly
# psalter; a feast changes only antiphons, chapter and prayer. Lauds and Vespers take the
# feast's psalms on greater feasts, so they keep matching by celebration first.
WEEKDAY_HOURS = frozenset({"prime", "terce", "sext", "none", "compline"})
NEIGHBOUR_DAYS = 3


def candidate_dates(
    day: date, index: Index | None, first_year: int = FIRST_YEAR, hour: str | None = None
) -> list[date]:
    """Dates whose recordings could stand in for `day` at `hour`, best first.

    Lauds, Vespers (and hour=None): the same celebration, same weekday first, then newest.
    Weekday hours: the right psalms matter most, so same weekday always comes first --
    same celebration, then the same week of the liturgical year, then the nearest
    calendar date -- and the celebration on another weekday is the last resort.
    """
    cel = index.celebration(day) if index is not None else None
    if cel is not None:
        feast = [d for d in index.dates_for(cel.key) if d <= day and d.year >= first_year]
    else:
        feast = _same_calendar_date(day, first_year)
    feast = _same_weekday_first(day, feast)
    if hour not in WEEKDAY_HOURS:
        return feast
    same_weekday = [d for d in feast if d.weekday() == day.weekday()]
    week = _same_liturgical_week(day, index, first_year) if cel is not None else []
    near = _nearest_same_weekday(day, first_year)
    return list(dict.fromkeys(same_weekday + week + near + feast))


def _same_calendar_date(day: date, first_year: int) -> list[date]:
    dates = []
    for year in range(day.year, first_year - 1, -1):
        try:
            dates.append(date(year, day.month, day.day))
        except ValueError:  # Feb 29 in a non-leap year
            pass
    return dates


def _same_weekday_first(day: date, dates: list[date]) -> list[date]:
    return sorted(dates, key=lambda d: d.weekday() != day.weekday())  # stable: keeps newest-first


def _same_liturgical_week(day: date, index: Index, first_year: int) -> list[date]:
    """The same weekday after the same Sunday in other years, newest first."""
    offset = (day.weekday() + 1) % 7  # days since the preceding Sunday
    sunday = index.celebration(day - timedelta(days=offset))
    if sunday is None:
        return []
    dates = [s + timedelta(days=offset) for s in index.dates_for(sunday.key) if s.weekday() == 6]
    return [d for d in dates if d <= day and d.year >= first_year]


def _nearest_same_weekday(day: date, first_year: int) -> list[date]:
    """In each earlier year, the date with day's weekday closest to day's calendar date."""
    dates = []
    for year in range(day.year - 1, first_year - 1, -1):
        base = date(year, day.month, min(day.day, 28 if day.month == 2 else day.day))
        delta = (day.weekday() - base.weekday() + NEIGHBOUR_DAYS) % 7 - NEIGHBOUR_DAYS
        dates.append(base + timedelta(days=delta))
    return dates


def episodes_for(
    day: date,
    get_day: Callable[[date], dict[str, str]] = fetch_day,
    index: Index | None = None,
    first_year: int = FIRST_YEAR,
) -> list[Episode]:
    cel = index.celebration(day) if index is not None else None
    name = cel.name if cel is not None else None
    fetched: dict[date, dict[str, str]] = {}
    episodes = []
    for hour in HOURS:
        for source in candidate_dates(day, index, first_year, hour):
            if source not in fetched:
                fetched[source] = get_day(source)
            url = fetched[source].get(hour)
            if url:
                src = index.celebration(source) if index is not None else None
                same = (src is not None and src.key == cel.key) if cel is not None else None
                episodes.append(Episode(day, hour, source, url, name, same, src.name if src else None))
                break
    return episodes
