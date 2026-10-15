from datetime import date, timedelta
from pathlib import Path

from barroux_daily.liturgy import Celebration, Index, celebrations, norm
from barroux_daily.ordo import WEEKDAYS, Row, assign_dates, parse_rows

FIX = Path(__file__).parent / "fixtures"


def dated(name, starts):
    html = (FIX / name).read_text(encoding="utf-8", errors="replace")
    return assign_dates(parse_rows(html), starts)


def week(start, names):
    """Consecutive days from start, one Row per name."""
    rows = {}
    for i, name in enumerate(names):
        d = start + timedelta(days=i)
        rows[d] = Row(d.day, WEEKDAYS[d.weekday()], name)
    return rows


def test_norm_strips_titles_ranks_punctuation_and_aliases_spelling_drift():
    assert norm("St. Teresa of Avila, Virgin") == "teresa of jesus"
    assert norm("St. Teresa of Jesus, Virgin & Doctor") == "teresa of jesus"
    assert norm("Twenty-First Sunday after Pentecost") == "twenty first sunday after pentecost"
    assert norm("First Sunday of Advent (Preface of Advent)") == "first sunday of advent"
    assert norm("Ss Ursula & Companions") == "ursula companions"


def test_feria_key_is_anchored_to_the_preceding_temporal_sunday():
    rows = week(date(2026, 10, 11), ["Twentieth Sunday after Pentecost", "Feria", "St. Hedwig, Widow", "Feria"])
    idx = celebrations(rows)
    assert idx.celebration(date(2026, 10, 12)).key == "feria|twentieth sunday after pentecost|monday"
    assert idx.celebration(date(2026, 10, 12)).name == "Monday after Twentieth Sunday after Pentecost"
    assert idx.celebration(date(2026, 10, 13)).key == "hedwig"
    assert idx.celebration(date(2026, 10, 14)).key == "feria|twentieth sunday after pentecost|wednesday"


def test_displaced_sunday_gets_a_week_suffix_so_keys_stay_unique_within_a_year():
    names = ["Twentieth Sunday after Pentecost", "Feria"] + ["Feria"] * 5 + ["Dedication of a Basilica", "Feria"]
    idx = celebrations(week(date(2026, 10, 11), names))
    first_monday = idx.celebration(date(2026, 10, 12)).key
    second_monday = idx.celebration(date(2026, 10, 19)).key
    assert first_monday == "feria|twentieth sunday after pentecost|monday"
    assert second_monday == "feria|twentieth sunday after pentecost+1|monday"
    assert first_monday != second_monday


def test_feria_with_no_anchor_still_gets_a_unique_key():
    idx = celebrations(week(date(2026, 10, 12), ["Feria"]))
    assert idx.celebration(date(2026, 10, 12)).key == "feria|2026-10-12"
    assert idx.celebration(date(2026, 10, 12)).name == "Feria"


def test_gap_between_merged_pages_resets_the_sunday_anchor():
    rows = week(date(2026, 10, 11), ["Twentieth Sunday after Pentecost", "Feria"])
    rows.update(week(date(2026, 12, 7), ["Feria", "Feria"]))
    idx = celebrations(rows)
    assert idx.celebration(date(2026, 10, 12)).key == "feria|twentieth sunday after pentecost|monday"
    assert idx.celebration(date(2026, 12, 7)).key == "feria|2026-12-07"
    assert idx.celebration(date(2026, 12, 7)).name == "Feria"
    assert idx.celebration(date(2026, 12, 8)).key == "feria|2026-12-08"


def test_two_consecutive_displaced_sundays_give_plus_one_then_plus_two():
    names = ["Twentieth Sunday after Pentecost"] + ["Feria"] * 6 + ["Dedication of a Basilica", "Feria"] * 1
    names += ["Feria"] * 5 + ["St. Hedwig", "Feria"]
    idx = celebrations(week(date(2026, 10, 11), names))
    assert idx.celebration(date(2026, 10, 19)).key == "feria|twentieth sunday after pentecost+1|monday"
    assert idx.celebration(date(2026, 10, 26)).key == "feria|twentieth sunday after pentecost+2|monday"


def test_temporal_sunday_after_a_displaced_one_resets_the_suffix():
    names = ["Twentieth Sunday after Pentecost"] + ["Feria"] * 6
    names += ["Dedication of a Basilica"] + ["Feria"] * 6
    names += ["Twenty-First Sunday after Pentecost", "Feria"]
    idx = celebrations(week(date(2026, 10, 11), names))
    assert idx.celebration(date(2026, 10, 26)).key == "feria|twenty first sunday after pentecost|monday"


def test_index_lookup_newest_first_and_unknown_cases():
    a, b, c = date(2024, 5, 1), date(2025, 5, 1), date(2026, 5, 1)
    idx = Index({a: Celebration("k", "K"), b: Celebration("k", "K"), c: Celebration("z", "Z")})
    assert idx.dates_for("k") == [b, a]
    assert idx.dates_for("nope") == []
    assert idx.celebration(date(2000, 1, 1)) is None
    assert idx.span() == (a, c)
    assert idx.lonely_keys() == ["z"]
    assert len(idx) == 3


def test_index_json_round_trip(tmp_path):
    idx = Index({date(2026, 10, 15): Celebration("teresa of jesus", "St. Teresa of Jesus")})
    path = tmp_path / "sub" / "idx.json"
    idx.save(path)
    again = Index.load(path)
    assert again.celebration(date(2026, 10, 15)) == Celebration("teresa of jesus", "St. Teresa of Jesus")


def test_real_ordo_pages_match_the_same_celebration_across_years():
    rows = {}
    rows.update(dated("ordo-2018-10.html", [(2018, 10)]))
    rows.update(dated("ordo-2019.html", [(2018, 11), (2018, 12)]))
    rows.update(dated("ordo-2026.html", [(2025, 11), (2025, 12)]))
    idx = celebrations(rows)

    teresa = idx.celebration(date(2026, 10, 15))
    assert teresa.key == "teresa of jesus"
    assert teresa.name == "St. Teresa of Jesus, Virgin & Doctor"
    assert idx.dates_for(teresa.key) == [date(2026, 10, 15), date(2019, 10, 15), date(2018, 10, 15)]

    sunday = idx.celebration(date(2026, 10, 18))
    assert sunday.key == idx.celebration(date(2018, 10, 14)).key == "twenty first sunday after pentecost"

    # A feria lands on the same liturgical day even when the calendar date differs.
    feria = idx.celebration(date(2026, 10, 21))
    assert feria.key == "feria|twenty first sunday after pentecost|wednesday"
    assert idx.dates_for(feria.key) == [date(2026, 10, 21), date(2019, 11, 6)]


def test_real_ordo_feria_keys_are_unique_within_a_calendar_year():
    rows = {}
    rows.update(dated("ordo-2018-10.html", [(2018, 10)]))
    rows.update(dated("ordo-2019.html", [(2018, 11), (2018, 12)]))
    rows.update(dated("ordo-2026.html", [(2025, 11), (2025, 12)]))
    idx = celebrations(rows)
    seen = {}
    for d in sorted(rows):
        key = idx.celebration(d).key
        if key.startswith("feria|"):
            assert (d.year, key) not in seen, (key, seen[(d.year, key)], d)
            seen[(d.year, key)] = d
