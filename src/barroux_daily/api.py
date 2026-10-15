from __future__ import annotations

import http.client
import json
import time
import urllib.error
import urllib.request
from datetime import date
from typing import Callable, TypeVar

API = "https://barrouxchant.com/api/hours/{d}.json"
USER_AGENT = "barroux-daily/0.1 (personal podcast feed)"
_sleep = time.sleep  # patched in tests
BACKOFF = (1, 3)  # seconds before the 2nd and 3rd attempts

T = TypeVar("T")


def _transient(err: Exception) -> bool:
    if isinstance(err, urllib.error.HTTPError):
        return err.code >= 500
    return isinstance(err, (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException))


def _retry(attempt: Callable[[], T]) -> T:
    """Run attempt, retrying network errors, timeouts and 5xx; 404 and other 4xx raise at once."""
    for wait in BACKOFF:
        try:
            return attempt()
        except Exception as err:
            if not _transient(err):
                raise
        _sleep(wait)
    return attempt()


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    def attempt() -> bytes:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read()

    return _retry(attempt)


def fetch_day(d: date, get: Callable[[str], bytes] = http_get) -> dict[str, str]:
    """Return {hour: mp3 url} for a day. Empty/404 days give {}; other errors raise."""
    try:
        data = json.loads(get(API.format(d=d.isoformat())))
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return {}
        raise
    return {
        hour: url
        for hour, url in data.items()
        if isinstance(url, str) and url.startswith("https://")
    }


def head_length(url: str) -> int | None:
    """Content-Length of a file (0 if the header is absent); None if it 404s."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})

    def attempt() -> int:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return int(resp.headers.get("Content-Length") or 0)

    try:
        return _retry(attempt)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise
