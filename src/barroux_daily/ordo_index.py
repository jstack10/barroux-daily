from __future__ import annotations

import os
import sys
import time
import urllib.error
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Sequence

from .api import http_get
from .liturgy import Index, celebrations
from .ordo import Row, assign_dates, parse_rows

MONTHLY = "https://propria.org/calendar/liturgical-calendar-{y}-{m:02d}/"
ANNUAL = ("https://propria.org/archived-{y}/", "https://propria.org/ordo-{y}/")


@dataclass(frozen=True)
class Page:
    urls: tuple[str, ...]
    starts: tuple[tuple[int, int], ...]
    required: bool = True


def default_pages(this_year: int) -> list[Page]:
    pages = [
        Page((MONTHLY.format(y=y, m=m),), ((y, m),))
        for y, last in ((2017, 12), (2018, 11))
        for m in range(1, last + 1)
    ]
    for y in range(2019, this_year + 2):
        pages.append(
            Page(
                tuple(u.format(y=y) for u in ANNUAL),
                ((y - 1, 11), (y - 1, 12)),
                required=y <= this_year,
            )
        )
    return pages


def fetch_page(url: str) -> str:
    time.sleep(1)  # be polite to propria.org
    return http_get(url).decode("utf-8", errors="replace")


def build_index(pages: Sequence[Page], fetch: Callable[[str], str]) -> Index:
    rows: dict[date, Row] = {}
    for page in pages:
        parsed: list[Row] = []
        for url in page.urls:
            try:
                parsed = parse_rows(fetch(url))
            except urllib.error.HTTPError as err:
                if err.code != 404:
                    raise
                continue
            if parsed:
                break
        if not parsed:
            if page.required:
                raise RuntimeError(f"no usable ordo page among {page.urls}")
            continue
        rows.update(assign_dates(parsed, page.starts))
    return celebrations(rows)


def main() -> None:
    out = Path(os.environ.get("ORDO_INDEX", "data/ordo_index.json"))
    index = build_index(default_pages(date.today().year), fetch_page)
    index.save(out)
    first, last = index.span()
    print(f"wrote {out}: {len(index)} days, {first} to {last}")
    lonely = index.lonely_keys()
    print(f"{len(lonely)} keys appear on only one date (look for spelling variants to alias):")
    for key in lonely[:40]:
        print(f"  {key}", file=sys.stdout)


if __name__ == "__main__":
    main()
