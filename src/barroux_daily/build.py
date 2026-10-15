from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from .api import fetch_day, head_length
from .episodes import Episode, episodes_for
from .feed import render_feed
from .liturgy import Index

WINDOW_DAYS = 7

INDEX = """<!doctype html>
<meta charset="utf-8">
<title>Barroux Chant: Today's Office</title>
<p>Private podcast feed. Add this URL to your podcast app:</p>
<p><a href="FEED_URL">FEED_URL</a></p>
"""


def local_today(tz: str, now_utc: datetime) -> date:
    return now_utc.astimezone(ZoneInfo(tz)).date()


def load_index(path: Path) -> Index | None:
    if not path.exists():
        print(f"warning: ordo index {path} not found; matching by calendar date", file=sys.stderr)
        return None
    return Index.load(path)


def build_feed(
    today: date,
    get_day: Callable[[date], dict[str, str]],
    probe: Callable[[str], int | None],
    tz: str,
    base_url: str,
    index: Index | None = None,
    window: int = WINDOW_DAYS,
) -> bytes:
    items: list[tuple[Episode, int]] = []
    for back in range(window):
        day = today - timedelta(days=back)
        if index is not None and index.celebration(day) is None:
            print(f"warning: {day} is not in the ordo index; matching by calendar date", file=sys.stderr)
        for ep in episodes_for(day, get_day, index):
            length = probe(ep.url)
            if length is None:
                print(f"skipping {ep.url}: 404 on CDN", file=sys.stderr)
                continue
            items.append((ep, length))
    if not items:
        raise RuntimeError("no episodes found; refusing to publish an empty feed")
    return render_feed(items, tz, base_url)


def main() -> None:
    tz = os.environ.get("FEED_TZ", "America/New_York")
    base_url = os.environ.get("FEED_BASE_URL", "http://localhost:8000").rstrip("/")
    out = Path(os.environ.get("OUT_DIR", "public"))
    index = load_index(Path(os.environ.get("ORDO_INDEX", "data/ordo_index.json")))
    today = local_today(tz, datetime.now(timezone.utc))
    xml = build_feed(today, fetch_day, head_length, tz, base_url, index)
    out.mkdir(parents=True, exist_ok=True)
    (out / "feed.xml").write_bytes(xml)
    (out / "index.html").write_text(INDEX.replace("FEED_URL", f"{base_url}/feed.xml"))
    print(f"wrote {out / 'feed.xml'} for {today}")


if __name__ == "__main__":
    main()
