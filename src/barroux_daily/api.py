from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date
from typing import Callable

API = "https://barrouxchant.com/api/hours/{d}.json"
USER_AGENT = "barroux-daily/0.1 (personal podcast feed)"


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


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
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return int(resp.headers.get("Content-Length") or 0)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise
