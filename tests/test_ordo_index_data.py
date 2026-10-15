"""Checks over the committed data/ordo_index.json (regenerate with `python -m barroux_daily.ordo_index`)."""

from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import pytest

from barroux_daily.liturgy import RECURRING, Index, liturgical_year

INDEX = Path(__file__).parent.parent / "data" / "ordo_index.json"


@pytest.fixture(scope="module")
def idx():
    return Index.load(INDEX)


def test_recurring_allowlist_is_only_the_saturday_office_of_our_lady():
    # The Saturday Office of Our Lady is the same Office every free Saturday; nothing else
    # in the ordo is genuinely one Office on several days of a liturgical year.
    assert RECURRING == {"saturday of our lady"}


def test_no_key_repeats_within_a_liturgical_year(idx):
    seen = defaultdict(list)
    first, last = idx.span()
    d = first
    while d <= last:
        c = idx.celebration(d)
        if c is not None and c.key not in RECURRING:
            seen[(liturgical_year(d), c.key)].append(d)
        d += timedelta(days=1)
    repeats = {}
    for (year, key), days in seen.items():
        if len(days) < 2:
            continue
        # A liturgical year can run 371 days (Advent 1 on Nov 27, next on Dec 3), so a fixed
        # feast on Nov 27..Dec 2 (St. Andrew, St. Bibiana) falls in it twice, a calendar year apart.
        if len({x.strftime("%m-%d") for x in days}) == 1 and len({x.year for x in days}) == len(days):
            continue
        repeats[(year, key)] = days
    assert repeats == {}


def test_greater_ferias_of_advent_are_filled_from_the_same_calendar_date(idx):
    key = idx.celebration(date(2025, 12, 23)).key
    assert {(d.month, d.day) for d in idx.dates_for(key)} == {(12, 23)}
    assert len(idx.dates_for(key)) > 1


def test_lent_and_september_ember_days_never_share_a_key(idx):
    keys = {c.key for c in map(idx.celebration, _days(*idx.span())) if c is not None}
    assert {"ember|lent|wednesday", "ember|september|wednesday"} <= keys
    for key in {k for k in keys if k.startswith("ember|")}:
        months = {d.month for d in idx.dates_for(key)}
        season = key.split("|")[1]
        assert months <= {"lent": {2, 3}, "pentecost": {5, 6}, "september": {9}, "advent": {12}}[season], key
    assert idx.celebration(date(2026, 2, 25)).key == "ember|lent|wednesday"
    assert all(d.month in (2, 3) for d in idx.dates_for("ember|lent|wednesday"))


def _days(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def test_septuagesima_to_low_sunday_2025_all_have_an_earlier_match(idx):
    missing = [d for d in _days(date(2025, 2, 16), date(2025, 4, 27)) if not idx.has_earlier(d)]
    assert missing == []


def test_lent_2026_sundays_have_an_earlier_match(idx):
    sundays = [date(2026, 2, 22) + timedelta(weeks=i) for i in range(6)]  # Lent 1..4, Passion, Palm
    assert [d for d in sundays if not idx.has_earlier(d)] == []


@pytest.mark.parametrize(
    "d",
    [
        date(2026, 10, 11),  # The Twentieth Sunday after Pentecost
        date(2026, 10, 12),
        date(2026, 10, 13),  # St. Edward
        date(2026, 11, 2),  # 1. Commemoration of All Souls
        # ferias after Christ the King and All Saints displaced the Sundays
        date(2026, 10, 29),
        date(2026, 11, 3),
        date(2026, 11, 5),
        date(2026, 11, 6),
    ],
)
def test_current_window_days_have_an_earlier_match(idx, d):
    assert idx.has_earlier(d), idx.celebration(d)
