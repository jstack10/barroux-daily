import json
import urllib.error
from datetime import date

import pytest

from barroux_daily import api
from barroux_daily.api import fetch_day, head_length

LAUDS = "https://cdn.barrouxchant.com/2025-10-15-lauds.mp3"


def test_fetch_day_maps_hour_to_url_and_requests_the_right_endpoint():
    seen = []

    def get(url):
        seen.append(url)
        return json.dumps({"lauds": LAUDS}).encode()

    assert fetch_day(date(2025, 10, 15), get) == {"lauds": LAUDS}
    assert seen == ["https://barrouxchant.com/api/hours/2025-10-15.json"]


def test_empty_day_is_empty_dict():
    assert fetch_day(date(2026, 10, 15), lambda url: b"{}") == {}


def test_404_is_an_empty_day():
    def get(url):
        raise urllib.error.HTTPError(url, 404, "not found", None, None)

    assert fetch_day(date(2013, 1, 1), get) == {}


def test_server_errors_propagate_so_the_build_fails():
    def get(url):
        raise urllib.error.HTTPError(url, 500, "boom", None, None)

    with pytest.raises(urllib.error.HTTPError):
        fetch_day(date(2025, 10, 15), get)


def test_junk_values_are_ignored():
    body = json.dumps({"lauds": None, "prime": "http://insecure/x.mp3", "terce": LAUDS}).encode()
    assert fetch_day(date(2025, 10, 15), lambda url: body) == {"terce": LAUDS}


class _FakeResponse:
    def __init__(self, headers):
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_head_length_reads_content_length_and_uses_head(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["method"] = req.get_method()
        seen["ua"] = req.get_header("User-agent")
        return _FakeResponse({"Content-Length": "46082089"})

    monkeypatch.setattr(api.urllib.request, "urlopen", fake_urlopen)
    assert head_length(LAUDS) == 46082089
    assert seen == {"method": "HEAD", "ua": api.USER_AGENT}


def test_head_length_missing_header_is_zero(monkeypatch):
    monkeypatch.setattr(api.urllib.request, "urlopen", lambda req, timeout: _FakeResponse({}))
    assert head_length(LAUDS) == 0


def test_head_length_404_is_none_but_other_errors_raise(monkeypatch):
    def not_found(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, "nf", None, None)

    def boom(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 503, "down", None, None)

    monkeypatch.setattr(api.urllib.request, "urlopen", not_found)
    assert head_length(LAUDS) is None
    monkeypatch.setattr(api.urllib.request, "urlopen", boom)
    with pytest.raises(urllib.error.HTTPError):
        head_length(LAUDS)
