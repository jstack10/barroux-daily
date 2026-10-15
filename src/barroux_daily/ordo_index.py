from __future__ import annotations

import difflib
import os
import sys
import time
import urllib.error
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Sequence

from .api import http_get
from .liturgy import Index, advent_sunday, celebrations, liturgical_year
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


_COUNTERS = set(
    "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth "
    "fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth twenty last "
    "monday tuesday wednesday thursday friday saturday sunday".split()
)


def _skeleton(key: str) -> list[str]:
    return [w for w in key.split() if w not in _COUNTERS]


def near_duplicates(keys: list[str], cutoff: float = 0.85) -> list[tuple[str, str, float]]:
    """Pairs of similar keys (likely spelling variants).

    Structured `x|y` keys are skipped, and so are pairs that differ only in an ordinal or a
    weekday ("eighth" / "eighteenth sunday after pentecost"), which are different days.
    """
    plain = sorted(k for k in set(keys) if "|" not in k)
    pairs = []
    for i, a in enumerate(plain):
        for b in plain[i + 1 :]:
            if _skeleton(a) == _skeleton(b):
                continue
            m = difflib.SequenceMatcher(None, a, b)
            if m.real_quick_ratio() >= cutoff and m.quick_ratio() >= cutoff and m.ratio() >= cutoff:
                pairs.append((a, b, m.ratio()))
    return pairs


def newest_full_liturgical_year(index: Index) -> int | None:
    """The latest liturgical year (Advent to Advent) that the index covers completely."""
    first, last = index.span()
    year = liturgical_year(last)
    while advent_sunday(year - 1) >= first:
        if advent_sunday(year) - timedelta(days=1) <= last:
            return year
        year -= 1
    return None


def main() -> None:
    out = Path(os.environ.get("ORDO_INDEX", "data/ordo_index.json"))
    index = build_index(default_pages(date.today().year), fetch_page)
    first, last = index.span()
    if out.exists():
        old_first, old_last = Index.load(out).span()
        if first > old_first or last < old_last:
            print(
                f"refusing to write {out}: new span {first} to {last} is shorter than the existing "
                f"{old_first} to {old_last} (a page probably failed to scrape)",
                file=sys.stderr,
            )
            sys.exit(1)
    index.save(out)
    print(f"wrote {out}: {len(index)} days, {first} to {last}")

    lonely = index.lonely_keys()
    print(f"{len(lonely)} keys appear on only one date (look for spelling variants to alias):")
    for key in lonely:
        print(f"  {key}")

    dupes = near_duplicates(index.keys())
    print(f"{len(dupes)} near-duplicate key pairs (alias them if they are the same celebration):")
    for a, b, ratio in dupes:
        print(f"  {a} ~ {b} ({ratio:.2f})")

    year = newest_full_liturgical_year(index)
    if year is not None:
        start, end = advent_sunday(year - 1), advent_sunday(year) - timedelta(days=1)
        missing = index.unmatched(start, end)
        print(f"liturgical year {year} ({start} to {end}): {len(missing)} days with no earlier match")
        for d in missing:
            print(f"  {d} {index.celebration(d).key}")


if __name__ == "__main__":
    main()
