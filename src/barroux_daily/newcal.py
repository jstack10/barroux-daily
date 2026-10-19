"""The day's celebrations in the current (1969) General Roman Calendar, for reference."""
from __future__ import annotations

import json
import sys
from datetime import date
from typing import Callable

from .api import http_get

# Church Calendar API (calapi.inadiutorium.cz); serves HTTP only.
API = "http://calapi.inadiutorium.cz/api/v0/en/calendars/general-en/{d.year}/{d.month}/{d.day}"
LABELLED = {"solemnity", "feast", "memorial", "optional memorial"}


def new_calendar(d: date, get: Callable[[str], bytes] = http_get) -> str | None:
    """'Monday, 29th week in Ordinary Time · Saint X (optional memorial)', or None on any failure."""
    try:
        celebrations = json.loads(get(API.format(d=d)))["celebrations"]
        parts = [
            f"{c['title']} ({c['rank']})" if c.get("rank") in LABELLED else c["title"]
            for c in celebrations
        ]
    except Exception as err:  # reference only: never fail the build over it
        print(f"warning: new calendar lookup for {d} failed: {err}", file=sys.stderr)
        return None
    if not parts:
        print(f"warning: new calendar has nothing for {d}", file=sys.stderr)
        return None
    return " · ".join(parts)
