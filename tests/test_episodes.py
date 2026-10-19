from datetime import date

from barroux_daily.episodes import FIRST_YEAR, HOURS, Episode, candidate_dates, episodes_for
from barroux_daily.liturgy import Celebration, Index


def url(d, hour):
    return f"https://cdn.barrouxchant.com/{d.isoformat()}-{hour}.mp3"


def archive(spec):
    """spec: {date: [hours]} -> (get_day, calls); calls records every date queried."""
    calls = []

    def get_day(d):
        calls.append(d)
        return {h: url(d, h) for h in spec.get(d, [])}

    return get_day, calls


TERESA = Celebration("teresa", "St. Teresa of Jesus")
SUNDAY = Celebration("sunday21", "Twenty-First Sunday after Pentecost")


def teresa_index(*dates):
    return Index({d: TERESA for d in dates} | {date(2025, 10, 16): Celebration("hedwig", "St. Hedwig")})


def test_liturgical_match_picks_newest_recording_per_hour_in_canonical_order():
    d26, d25, d24 = date(2026, 10, 15), date(2025, 10, 15), date(2024, 10, 15)
    get_day, _ = archive({d25: ["vespers", "lauds"], d24: ["lauds", "prime"]})
    eps = episodes_for(d26, get_day, teresa_index(d26, d25, d24))
    assert [(e.hour, e.recorded) for e in eps] == [("lauds", d25), ("prime", d24), ("vespers", d25)]
    assert eps[0] == Episode(d26, "lauds", d25, url(d25, "lauds"), "St. Teresa of Jesus")


def test_recordings_from_a_different_calendar_date_are_used_when_the_celebration_matches():
    today, moved = date(2026, 10, 18), date(2019, 11, 3)
    get_day, calls = archive({moved: ["lauds"]})
    idx = Index({today: SUNDAY, moved: SUNDAY, date(2019, 10, 20): Celebration("other", "Other")})
    (ep,) = episodes_for(today, get_day, idx)
    assert ep.recorded == moved
    assert date(2019, 10, 20) not in calls  # same weekday-ish neighbours are never queried


def test_the_days_own_recording_wins_over_the_archive():
    d26, d25 = date(2026, 10, 15), date(2025, 10, 15)
    get_day, _ = archive({d26: ["lauds"], d25: ["lauds"]})
    (ep,) = episodes_for(d26, get_day, teresa_index(d26, d25))
    assert ep.recorded == d26


def test_unknown_is_never_published_and_the_hour_falls_back_to_an_earlier_year():
    d26, d25, d24 = date(2026, 10, 15), date(2025, 10, 15), date(2024, 10, 15)
    get_day, _ = archive({d25: ["unknown"], d24: ["compline"]})
    eps = episodes_for(d26, get_day, teresa_index(d26, d25, d24))
    assert [(e.hour, e.recorded) for e in eps] == [("compline", d24)]


def test_never_queries_the_future_or_before_first_year():
    day = date(2025, 10, 15)
    idx = Index({day: TERESA, date(2026, 10, 15): TERESA, date(2016, 10, 15): TERESA, date(2017, 10, 15): TERESA})
    assert candidate_dates(day, idx) == [day, date(2017, 10, 15)]


def test_stops_as_soon_as_every_hour_is_found():
    d26, d25, d24 = date(2026, 10, 15), date(2025, 10, 15), date(2024, 10, 15)
    get_day, calls = archive({d25: list(HOURS)})
    eps = episodes_for(d26, get_day, teresa_index(d26, d25, d24))
    assert len(eps) == 7
    assert calls == [d26, d25]


def test_nothing_anywhere_gives_empty_list():
    get_day, _ = archive({})
    assert episodes_for(date(2026, 10, 15), get_day, teresa_index(date(2026, 10, 15))) == []


def test_day_missing_from_the_index_falls_back_to_the_calendar_date_and_has_no_celebration():
    day = date(2027, 3, 4)
    older = date(2025, 3, 4)
    get_day, calls = archive({older: ["lauds"]})
    (ep,) = episodes_for(day, get_day, Index({date(2026, 10, 15): TERESA}))
    assert ep.recorded == older
    assert ep.celebration is None
    assert calls[0] == day and calls[1] == date(2021, 3, 4)  # same weekday (Thu) first


def test_no_index_at_all_also_falls_back_and_feb_29_skips_non_leap_years():
    get_day, calls = archive({date(2020, 2, 29): ["lauds"]})
    eps = episodes_for(date(2024, 2, 29), get_day, None)
    assert [(e.hour, e.recorded) for e in eps] == [("lauds", date(2020, 2, 29))]
    assert {d.year for d in calls} == {2024, 2020}
    assert all((d.month, d.day) == (2, 29) for d in calls)
    assert min(candidate_dates(date(2025, 10, 15), None)).year == FIRST_YEAR


def test_same_weekday_years_come_first_because_lesser_feasts_use_weekday_psalms():
    from barroux_daily.liturgy import Celebration, Index
    key = Celebration("peter of alcantara", "St. Peter of Alcantara")
    idx = Index({date(y, 10, 19): key for y in (2026, 2024, 2023, 2020, 2019)})
    assert candidate_dates(date(2026, 10, 19), idx) == [
        date(2026, 10, 19), date(2020, 10, 19), date(2024, 10, 19), date(2023, 10, 19), date(2019, 10, 19),
    ]


def test_calendar_fallback_also_prefers_the_same_weekday():
    assert candidate_dates(date(2026, 10, 19), None)[:3] == [date(2026, 10, 19), date(2020, 10, 19), date(2025, 10, 19)]
