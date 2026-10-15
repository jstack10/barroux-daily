import urllib.error
from datetime import date, timedelta
from pathlib import Path

import pytest

from barroux_daily.ordo_index import Page, build_index, default_pages

FIX = Path(__file__).parent / "fixtures"


def fixture(name):
    return (FIX / name).read_text(encoding="utf-8", errors="replace")


def fake_fetch(pages):
    def fetch(url):
        if url in pages:
            return pages[url]
        raise urllib.error.HTTPError(url, 404, "nf", None, None)

    return fetch


def test_default_pages_cover_2017_to_next_year_and_only_the_future_is_optional():
    pages = default_pages(2026)
    assert len(pages) == 32  # 23 monthly + annual 2019..2027
    assert pages[0].urls == ("https://propria.org/calendar/liturgical-calendar-2017-01/",)
    assert pages[0].starts == ((2017, 1),)
    assert pages[22].urls == ("https://propria.org/calendar/liturgical-calendar-2018-11/",)
    p2019 = pages[23]
    assert p2019.urls == ("https://propria.org/archived-2019/", "https://propria.org/ordo-2019/")
    assert p2019.starts == ((2018, 11), (2018, 12))
    assert [p.required for p in pages[23:]] == [True] * 8 + [False]
    assert pages[-1].urls[1] == "https://propria.org/ordo-2027/"


def test_build_index_merges_pages_and_falls_back_to_the_second_url():
    pages = [
        Page(("https://x/m-2018-10/",), ((2018, 10),)),
        Page(("https://x/archived-2026/", "https://x/ordo-2026/"), ((2025, 11), (2025, 12))),
        Page(("https://x/ordo-2027/",), ((2026, 11), (2026, 12)), required=False),
    ]
    fetch = fake_fetch(
        {
            "https://x/m-2018-10/": fixture("ordo-2018-10.html"),
            "https://x/ordo-2026/": fixture("ordo-2026.html"),
        }
    )
    idx = build_index(pages, fetch)
    assert idx.span() == (date(2018, 10, 1), date(2026, 11, 30))
    assert idx.celebration(date(2026, 10, 15)).key == "teresa of jesus"
    assert idx.celebration(date(2018, 10, 15)).key == "teresa of jesus"


def test_a_required_page_that_cannot_be_fetched_raises():
    pages = [Page(("https://x/missing/",), ((2018, 10),))]
    with pytest.raises(RuntimeError, match="missing"):
        build_index(pages, fake_fetch({}))


def test_a_page_with_no_table_rows_counts_as_unusable():
    pages = [Page(("https://x/a/", "https://x/b/"), ((2018, 10),))]
    fetch = fake_fetch({"https://x/a/": "<html>redirected home page</html>", "https://x/b/": fixture("ordo-2018-10.html")})
    assert len(build_index(pages, fetch)) == 31


def _index(first, last, keys=("k",)):
    from barroux_daily.liturgy import Celebration, Index

    entries = {}
    d, i = first, 0
    while d <= last:
        k = keys[i % len(keys)]
        entries[d] = Celebration(k, k)
        d += timedelta(days=1)
        i += 1
    return Index(entries)


def _run_main(monkeypatch, tmp_path, new_index):
    from barroux_daily import ordo_index

    out = tmp_path / "ordo_index.json"
    monkeypatch.setenv("ORDO_INDEX", str(out))
    monkeypatch.setattr(ordo_index, "build_index", lambda pages, fetch: new_index)
    return out, ordo_index.main


def test_main_refuses_to_write_an_index_whose_span_shrinks(monkeypatch, tmp_path, capsys):
    out, main = _run_main(monkeypatch, tmp_path, _index(date(2017, 1, 1), date(2026, 10, 31)))
    _index(date(2017, 1, 1), date(2026, 11, 30)).save(out)
    before = out.read_text()
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code not in (0, None)
    assert "2026-11-30" in capsys.readouterr().err
    assert out.read_text() == before


def test_main_refuses_when_the_start_moves_later(monkeypatch, tmp_path):
    out, main = _run_main(monkeypatch, tmp_path, _index(date(2019, 1, 1), date(2027, 11, 30)))
    _index(date(2017, 1, 1), date(2026, 11, 30)).save(out)
    with pytest.raises(SystemExit):
        main()


def test_main_writes_a_growing_index_and_reports_lonely_near_duplicate_and_unmatched(monkeypatch, tmp_path, capsys):
    from barroux_daily.liturgy import Celebration, Index

    entries = {}
    d = date(2024, 11, 1)
    n = 0
    while d <= date(2026, 11, 30):
        entries[d] = Celebration(f"feria|x|{n}", "Feria")  # all unique feria keys
        d += timedelta(days=1)
        n += 1
    lonely = [f"lonely saint number {i:02d}" for i in range(45)]
    for i, k in enumerate(lonely):
        entries[date(2025, 1, 1) + timedelta(days=i)] = Celebration(k, k)
    entries[date(2025, 3, 1)] = Celebration("bernardine of sienna", "x")
    entries[date(2025, 3, 2)] = Celebration("bernardine of siena", "x")
    entries[date(2025, 3, 3)] = Celebration("eighth sunday after pentecost", "x")
    entries[date(2025, 3, 4)] = Celebration("eighteenth sunday after pentecost", "x")
    out, main = _run_main(monkeypatch, tmp_path, Index(entries))
    _index(date(2024, 11, 1), date(2026, 10, 31)).save(out)
    main()
    text = capsys.readouterr().out
    assert Index.load(out).span() == (date(2024, 11, 1), date(2026, 11, 30))
    for k in lonely:  # all of them, not just the first 40
        assert f"  {k}\n" in text
    assert "bernardine of siena ~ bernardine of sienna" in text
    assert "feria|x|1 ~" not in text
    assert "eighteenth sunday after pentecost ~" not in text  # differ only in the ordinal
    # newest full liturgical year: Advent 2025 (Nov 30) to the Saturday before Advent 2026
    assert "liturgical year 2026 (2025-11-30 to 2026-11-28): 364 days with no earlier match" in text
