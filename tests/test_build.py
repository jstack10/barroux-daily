import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime

import pytest

from barroux_daily import build
from barroux_daily.build import build_feed, load_index, local_today
from barroux_daily.liturgy import Celebration, Index

BASE = "https://example.github.io/barroux-daily"
NY = "America/New_York"


def only_lauds(d):
    return {"lauds": f"https://cdn.barrouxchant.com/{d.isoformat()}-lauds.mp3"}


def guids(xml):
    return [g.text for g in ET.fromstring(xml).iterfind("channel/item/guid")]


def test_window_covers_today_and_previous_days():
    xml = build_feed(date(2026, 10, 15), only_lauds, lambda u: 10, NY, BASE, window=2, ahead=0)
    assert guids(xml) == ["barroux-daily:2026-10-15:lauds", "barroux-daily:2026-10-14:lauds"]


def test_feed_includes_tomorrow():
    xml = build_feed(date(2026, 10, 15), only_lauds, lambda u: 10, NY, BASE, window=1)
    assert guids(xml) == [
        "barroux-daily:2026-10-16:lauds",
        "barroux-daily:2026-10-15:lauds",
    ]


def test_no_episode_is_dated_after_the_build_day():
    xml = build_feed(date(2026, 10, 15), only_lauds, lambda u: 10, NY, BASE, window=1)
    dates = [parsedate_to_datetime(p.text).date() for p in ET.fromstring(xml).iterfind("channel/item/pubDate")]
    assert max(dates) == date(2026, 10, 15)


def test_default_feed_is_today_and_tomorrow():
    xml = build_feed(date(2026, 10, 15), only_lauds, lambda u: 10, NY, BASE)
    assert len(guids(xml)) == build.WINDOW_DAYS + build.AHEAD_DAYS == 2


def test_episode_whose_file_404s_is_dropped():
    def probe(url):
        return None if "2026-10-14" in url else 10

    xml = build_feed(date(2026, 10, 15), only_lauds, probe, NY, BASE, window=2, ahead=0)
    assert guids(xml) == ["barroux-daily:2026-10-15:lauds"]


def test_enclosure_length_comes_from_probe():
    xml = build_feed(date(2026, 10, 15), only_lauds, lambda u: 1234, NY, BASE, window=1, ahead=0)
    assert ET.fromstring(xml).find("channel/item/enclosure").get("length") == "1234"


def test_titles_use_the_index_celebration_name():
    idx = Index({date(2026, 10, 15): Celebration("teresa", "St. Teresa of Jesus")})
    xml = build_feed(date(2026, 10, 15), only_lauds, lambda u: 10, NY, BASE, index=idx, window=1, ahead=0)
    assert ET.fromstring(xml).findtext("channel/item/title") == "Thu Oct 15 · Lauds · St. Teresa of Jesus"


def test_refuses_to_publish_an_empty_feed():
    with pytest.raises(RuntimeError, match="empty feed"):
        build_feed(date(2026, 10, 15), lambda d: {}, lambda u: 10, NY, BASE)


def test_everything_404ing_also_refuses():
    with pytest.raises(RuntimeError, match="empty feed"):
        build_feed(date(2026, 10, 15), only_lauds, lambda u: None, NY, BASE)


def test_local_today_uses_the_feed_timezone_not_utc():
    three_am_utc = datetime(2026, 10, 15, 3, 0, tzinfo=timezone.utc)
    assert local_today("America/New_York", three_am_utc) == date(2026, 10, 14)
    assert local_today("Europe/London", three_am_utc) == date(2026, 10, 15)
    assert local_today("UTC", three_am_utc) == date(2026, 10, 15)


def test_load_index_returns_none_and_warns_when_the_file_is_missing(tmp_path, capsys):
    assert load_index(tmp_path / "nope.json") is None
    assert "ordo index" in capsys.readouterr().err


def test_main_writes_feed_and_index_even_without_an_ordo_index(tmp_path, monkeypatch):
    monkeypatch.setenv("OUT_DIR", str(tmp_path))
    monkeypatch.setenv("FEED_BASE_URL", BASE)
    monkeypatch.setenv("ORDO_INDEX", str(tmp_path / "missing.json"))
    monkeypatch.setattr(build, "fetch_day", only_lauds)
    monkeypatch.setattr(build, "head_length", lambda u: 10)
    monkeypatch.setattr(build, "new_calendar", lambda d: None)
    build.main()
    assert (tmp_path / "feed.xml").read_bytes().startswith(b"<?xml")
    assert f"{BASE}/feed.xml" in (tmp_path / "index.html").read_text()
    assert (tmp_path / "cover.jpg").read_bytes()[:3] == b"\xff\xd8\xff"


def test_descriptions_carry_the_new_calendar_day():
    looked_up = []

    def newcal(d):
        looked_up.append(d)
        return "Monday, 29th week in Ordinary Time"

    xml = build_feed(date(2026, 10, 19), only_lauds, lambda u: 10, NY, BASE, window=1, ahead=0,
                     lookup_new_calendar=newcal)
    desc = ET.fromstring(xml).findtext("channel/item/description")
    assert "New calendar: Monday, 29th week in Ordinary Time." in desc
    assert looked_up == [date(2026, 10, 19)]


def test_no_new_calendar_line_when_the_lookup_fails():
    xml = build_feed(date(2026, 10, 19), only_lauds, lambda u: 10, NY, BASE, window=1, ahead=0,
                     lookup_new_calendar=lambda d: None)
    assert "New calendar" not in ET.fromstring(xml).findtext("channel/item/description")
