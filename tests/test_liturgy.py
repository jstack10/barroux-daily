from datetime import date, timedelta
from pathlib import Path

from barroux_daily.liturgy import Celebration, Index, advent_sunday, celebrations, liturgical_year, norm
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


def test_feria_after_a_displaced_sunday_takes_the_next_ordinal_sunday():
    # Finding #4 changed this: the week of a displaced Sunday is that Sunday's week,
    # so it keys as the next ordinal instead of "<anchor>+1".
    names = ["Twentieth Sunday after Pentecost", "Feria"] + ["Feria"] * 5 + ["Dedication of a Basilica", "Feria"]
    idx = celebrations(week(date(2026, 10, 11), names))
    first_monday = idx.celebration(date(2026, 10, 12))
    second_monday = idx.celebration(date(2026, 10, 19))
    assert first_monday.key == "feria|twentieth sunday after pentecost|monday"
    assert second_monday.key == "feria|twenty first sunday after pentecost|monday"
    assert second_monday.name == "Monday after Twenty-First Sunday after Pentecost"


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


def test_two_consecutive_displaced_sundays_advance_the_ordinal_twice():
    names = ["Twentieth Sunday after Pentecost"] + ["Feria"] * 6 + ["Dedication of a Basilica", "Feria"] * 1
    names += ["Feria"] * 5 + ["St. Hedwig", "Feria"]
    idx = celebrations(week(date(2026, 10, 11), names))
    # Finding #4: ordinals advance instead of "+1"/"+2" suffixes.
    assert idx.celebration(date(2026, 10, 19)).key == "feria|twenty first sunday after pentecost|monday"
    assert idx.celebration(date(2026, 10, 26)).key == "feria|twenty second sunday after pentecost|monday"


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


def test_norm_folds_accents_numbering_leading_the_and_addendum():
    assert norm("St. Irenæus, Bishop & Martyr") == "irenaeus"
    assert norm("St. Raymond of Peñafort") == "raymond of penafort"
    assert norm("1. Commemoration of All Souls, The First Mass") == "commemoration of all souls"
    assert norm("Commemoration of All Souls, First Mass") == "commemoration of all souls"
    assert norm("The Twentieth Sunday after Pentecost") == "twentieth sunday after pentecost"
    assert norm("Ss Simon and Jude, Apostles") == norm("Ss Simon & Jude, Apostles") == "simon jude"
    assert norm("Septuagesima Sunday and Addendum") == "septuagesima sunday"
    assert norm("Wednesday of Holy Week; Office of Tenebræ") == "wednesday of holy week"
    assert norm("Wednesday of Holy Week; Office of Tenebrae") == "wednesday of holy week"
    assert norm("All Saints") == "all saints"


def test_norm_aliases_temporal_name_drift():
    for n in ("First", "Second", "Third", "Fourth"):
        assert norm(f"{n} Sunday in Lent") == norm(f"{n} Sunday of Lent") == f"{n.lower()} sunday of lent"
    assert norm("Dominica Resurrectionis") == norm("Easter Sunday") == "easter sunday"
    assert norm("Monday in the Octave of Easter") == norm("Easter Monday") == "easter monday"
    assert norm("Saturday in the Octave of Easter") == "easter saturday"
    assert norm("Monday in the Octave of Pentecost") == norm("Pentecost Monday") == "pentecost monday"
    assert norm("Dominica in Albis") == norm("Divine Mercy Sunday")
    assert norm("Holy Thursday") == norm("Maundy Thursday")
    assert norm("Easter Vigil Mass") == norm("Holy Saturday")
    assert norm("Solemn Easter Vigil and First Mass of Easter Sunday") == norm("Holy Saturday")
    assert norm("Good Friday Office and Mass of the Presanctified") == norm("Good Friday")
    assert norm("Twenty-Fourth and Last Sunday after Pentecost") == norm("Twenty-Fourth or Last Sunday after Pentecost")
    assert norm("Votive Mass: Saturday of Our Lady") == "saturday of our lady"


def test_norm_aliases_saint_spelling_drift():
    pairs = [
        ("St. Edward the Confessor, King", "St. Edward, King & Confessor"),
        ("St. Callistus I, Pope & Martyr", "St. Calistus I, Pope & Martyr"),
        ("St. Margaret Mary Alacocque, Virgin", "St. Margaret Mary Alacoque, Virgin"),
        ("St. Jerome Æmiliani, Confessor", "St. Jerome Emiliani, Confessor"),
        ("St. Joseph of Calasance, Confessor", "St. Joseph Calasance, Confessor"),
        ("St. Julia of Falconieri, Virgin", "St. Juliana Falconieri, Virgin"),
        ("St. Julia Falconieri, Virgin", "St. Juliana Falconieri, Virgin"),
        ("St. Lawrence Justinian, Bishop & Confessor", "St. Laurence Justinian, Bishop & Confessor"),
        ("St. Pascal Baylon, Confessor", "St. Paschal Baylon, Confessor"),
        ("St. Philip Benize, Confessor", "St. Philip Benizi, Confessor"),
        ("St. Stephan of Hungary, King & Confessor", "St. Stephen of Hungary, King & Confessor"),
        ("St. Ubaldus, Bishop & Confessor", "St. Ubald, Bishop & Confessor"),
        ("St. Anthony Mary Zaccariah, Confessor", "St. Anthony Mary Zaccaria, Confessor"),
        ("St. Bernardine of Sienna, Confessor", "St. Bernardine of Siena, Confessor"),
        ("St. Jane Frances Fremiot de Chantal, Widow", "St. Jane Frances de Chantal, Widow"),
        ("St. Thérèse of the Child Jesus and the Holy Face, Virgin & Doctor", "St. Theresa of the Child Jesus"),
        ("St. Theresa of the Infant Jesus, Virgin & Doctor", "St. Theresa of the Child Jesus"),
        ("The Seven Sorrows of the Blessed Virgin Mary", "Seven Sorrows of the Blessed Virgin Mary"),
    ]
    for a, b in pairs:
        assert norm(a) == norm(b), (a, b)


def test_greater_ferias_of_advent_key_by_calendar_date():
    names = ["Third Sunday of Advent"] + ["Greater Feria of Advent"] * 6
    idx = celebrations(week(date(2025, 12, 14), names[:1] + ["Feria"] * 2 + names[1:]))
    # Dec 14 Sunday, 15-16 Feria, 17-22 Greater Feria
    keys = [idx.celebration(date(2025, 12, d)).key for d in range(17, 23)]
    assert keys == [f"greater feria of advent|12-{d}" for d in range(17, 23)]
    assert idx.celebration(date(2025, 12, 17)).name == "Greater Feria of Advent"


def test_ember_days_key_by_season_from_the_month_not_the_wording():
    rows = {}
    rows.update(week(date(2026, 2, 25), ["Ember Wednesday"]))
    rows.update(week(date(2025, 3, 12), ["Ember Wednesday of Lent"]))
    rows.update(week(date(2024, 9, 18), ["Ember Wednesday"]))
    rows.update(week(date(2025, 9, 24), ["Ember Wednesday in September"]))
    rows.update(week(date(2025, 6, 11), ["Ember Wednesday in the Octave of Pentecost"]))
    rows.update(week(date(2017, 6, 7), ["Pentecost Wednesday"]))
    rows.update(week(date(2025, 12, 20), ["Ember Saturday of Advent"]))
    idx = celebrations(rows)
    assert idx.celebration(date(2026, 2, 25)).key == "ember|lent|wednesday"
    assert idx.celebration(date(2025, 3, 12)).key == "ember|lent|wednesday"
    assert idx.celebration(date(2024, 9, 18)).key == "ember|september|wednesday"
    assert idx.celebration(date(2025, 9, 24)).key == "ember|september|wednesday"
    assert idx.celebration(date(2025, 6, 11)).key == "ember|pentecost|wednesday"
    assert idx.celebration(date(2017, 6, 7)).key == "ember|pentecost|wednesday"
    assert idx.celebration(date(2025, 12, 20)).key == "ember|advent|saturday"
    assert idx.celebration(date(2026, 2, 25)).name == "Ember Wednesday"


def _displaced(anchor, start):
    """anchor Sunday, six ferias, a feast on Sunday, then a Monday feria."""
    return celebrations(week(start, [anchor] + ["Feria"] * 6 + ["Some Feast", "Feria"])).celebration(
        start + timedelta(days=8)
    )


def test_displaced_ordinal_respects_season_caps():
    assert _displaced("Third Sunday after Easter", date(2026, 4, 26)).key == "feria|fourth sunday after easter|monday"
    assert _displaced("Fifth Sunday after Easter", date(2026, 5, 10)).key == "feria|fifth sunday after easter+1|monday"
    assert _displaced("Twenty-Second Sunday after Pentecost", date(2026, 10, 25)).key == (
        "feria|twenty third sunday after pentecost|monday"
    )
    # after the 23rd come the resumed Epiphany Sundays, so never map to a 24th
    c = _displaced("Twenty-Third Sunday after Pentecost", date(2026, 11, 1))
    assert c.key == "feria|twenty third sunday after pentecost+1|monday"
    assert c.name == "Monday after Twenty-Third Sunday after Pentecost (+1 wk)"
    assert _displaced("Second Sunday of Advent", date(2025, 12, 7)).key == "feria|third sunday of advent|monday"
    assert _displaced("Fourth Sunday of Advent", date(2025, 12, 21)).key == "feria|fourth sunday of advent+1|monday"
    assert _displaced("First Sunday in Lent", date(2026, 2, 22)).key == "feria|second sunday of lent|monday"
    assert _displaced("Fourth Sunday of Lent", date(2026, 3, 15)).key == "feria|fourth sunday of lent+1|monday"
    assert _displaced("Third Sunday after Epiphany", date(2026, 1, 25)).key == "feria|fourth sunday after epiphany|monday"
    assert _displaced("Sixth Sunday after Epiphany", date(2026, 1, 25)).key == "feria|sixth sunday after epiphany+1|monday"
    # no ordinal: keep the suffix
    assert _displaced("Resumed Sixth Sunday after Epiphany", date(2026, 11, 8)).key == (
        "feria|resumed sixth sunday after epiphany+1|monday"
    )


def test_liturgical_year_starts_on_the_first_sunday_of_advent():
    assert advent_sunday(2025) == date(2025, 11, 30)
    assert advent_sunday(2023) == date(2023, 12, 3)
    assert advent_sunday(2026) == date(2026, 11, 29)
    assert liturgical_year(date(2025, 11, 29)) == 2025
    assert liturgical_year(date(2025, 11, 30)) == 2026


def test_has_earlier_and_unmatched():
    a, b, c = date(2024, 5, 1), date(2025, 5, 1), date(2025, 6, 1)
    idx = Index({a: Celebration("k", "K"), b: Celebration("k", "K"), c: Celebration("z", "Z")})
    assert idx.has_earlier(b) and not idx.has_earlier(a) and not idx.has_earlier(c)
    assert idx.unmatched(date(2025, 1, 1), date(2025, 12, 31)) == [c]
