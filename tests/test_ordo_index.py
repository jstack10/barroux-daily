import urllib.error
from datetime import date
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
