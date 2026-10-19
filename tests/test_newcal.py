import json
import urllib.error
from datetime import date

from barroux_daily.newcal import new_calendar

MON = {
    "date": "2026-10-19",
    "celebrations": [
        {"title": "Monday, 29th week in Ordinary Time", "rank": "ferial"},
        {"title": "Saint Paul of the Cross, priest", "rank": "optional memorial"},
    ],
}


def test_formats_the_day_with_ranks_for_saints():
    seen = []

    def get(url):
        seen.append(url)
        return json.dumps(MON).encode()

    assert new_calendar(date(2026, 10, 19), get) == (
        "Monday, 29th week in Ordinary Time · Saint Paul of the Cross, priest (optional memorial)"
    )
    assert seen == ["http://calapi.inadiutorium.cz/api/v0/en/calendars/general-en/2026/10/19"]


def test_solemnity_is_labelled():
    data = {"celebrations": [{"title": "The Nativity of the Lord", "rank": "solemnity"}]}
    assert new_calendar(date(2026, 12, 25), lambda u: json.dumps(data).encode()) == (
        "The Nativity of the Lord (solemnity)"
    )


def test_any_failure_gives_none_and_never_breaks_the_build(capsys):
    def boom(url):
        raise urllib.error.URLError("down")

    assert new_calendar(date(2026, 10, 19), boom) is None
    assert new_calendar(date(2026, 10, 19), lambda u: b"not json") is None
    assert new_calendar(date(2026, 10, 19), lambda u: b'{"celebrations": []}') is None
    assert "new calendar" in capsys.readouterr().err
