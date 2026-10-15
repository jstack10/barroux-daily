from datetime import date
from pathlib import Path

import pytest

from barroux_daily.ordo import Row, assign_dates, parse_rows

FIX = Path(__file__).parent / "fixtures"


def page(name):
    return (FIX / name).read_text(encoding="utf-8", errors="replace")


def test_monthly_page_gives_one_row_per_day():
    rows = parse_rows(page("ordo-2018-10.html"))
    assert [r.day for r in rows] == list(range(1, 32))
    by_day = {r.day: r for r in rows}
    assert by_day[15] == Row(15, "Monday", "St. Teresa of Avila, Virgin")
    assert by_day[14].name == "Twenty-First Sunday after Pentecost"


def test_annual_page_skips_alternate_rows():
    rows = parse_rows(page("ordo-2026.html"))
    assert len(rows) == 366
    assert rows[0].name.startswith("First Sunday of Advent")


def test_headers_and_blank_date_rows_are_ignored():
    html = (
        "<table><tr><td>Date</td><td>Day</td><td>The Mass</td></tr>"
        "<tr><td>3</td><td>Tuesday</td><td>St. Hedwig<em>, Widow</em><br>(or: X)</td><td>3</td></tr>"
        "<tr><td>&nbsp;</td><td>&nbsp;</td><td>in Carmelite churches: Y</td></tr></table>"
    )
    assert parse_rows(html) == [Row(3, "Tuesday", "St. Hedwig, Widow")]


def test_assign_dates_for_a_monthly_page():
    dated = assign_dates(parse_rows(page("ordo-2018-10.html")), [(2018, 10)])
    assert dated[date(2018, 10, 15)].name == "St. Teresa of Avila, Virgin"
    assert len(dated) == 31


def test_assign_dates_infers_the_start_month_of_an_annual_page():
    dated = assign_dates(parse_rows(page("ordo-2026.html")), [(2025, 11), (2025, 12)])
    assert min(dated) == date(2025, 11, 30)
    assert max(dated) == date(2026, 11, 30)
    assert dated[date(2026, 10, 15)].name == "St. Teresa of Jesus, Virgin & Doctor"
    assert dated[date(2026, 10, 18)].name == "Twenty-First Sunday after Pentecost"
    assert dated[date(2026, 10, 21)].name == "Feria"


def test_assign_dates_tries_the_next_candidate_start():
    dated = assign_dates(parse_rows(page("ordo-2019.html")), [(2018, 11), (2018, 12)])
    assert min(dated) == date(2018, 12, 1)


def test_wrong_start_month_raises():
    with pytest.raises(ValueError, match="weekday"):
        assign_dates(parse_rows(page("ordo-2018-10.html")), [(2018, 9)])


def _week(days):
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    # 2018-10-01 is a Monday; weekday and name follow position, the printed day is as given
    return [Row(d, names[i % 7], f"r{i + 1}") for i, d in enumerate(days)]


def test_a_mistyped_day_cell_is_dated_sequentially_and_warns(capsys):
    rows = _week([1, 2, 3, 1, 5, 6, 7])  # fourth row should say 4
    dated = assign_dates(rows, [(2018, 10)])
    assert dated[date(2018, 10, 4)].name == "r4"
    assert len(dated) == 7
    assert "warning" in capsys.readouterr().err


def test_a_duplicated_row_still_raises():
    rows = _week([1, 2, 3, 4, 5, 6, 7])
    rows.insert(3, rows[2])  # the Wednesday row appears twice
    with pytest.raises(ValueError, match="weekday"):
        assign_dates(rows, [(2018, 10)])
