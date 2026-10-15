# Barroux Daily Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A private podcast feed that gives me, every day, the Gregorian chant of the Divine Office for today's *liturgical* day, assembled from barrouxchant.com's archive of past years, so I can pray with it.

**Architecture:** A committed index (`data/ordo_index.json`), built from the propria.org ordo, maps every date 2017 to now to a liturgical key (saint, named day, or "weekday after Sunday X"). The daily build finds earlier dates with the same key, takes the newest barrouxchant.com recording of each canonical hour, and renders an RSS feed whose enclosures point at the site's CDN. GitHub Actions rebuilds it daily and publishes to GitHub Pages. No audio is hosted by us.

**Tech Stack:** Python 3.11+ (stdlib only: `urllib`, `html.parser`, `xml.etree`, `zoneinfo`, `json`), pytest, GitHub Actions, GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-10-15-barroux-daily-design.md`

## Global Constraints

- Python `>=3.11`, zero runtime dependencies (dev dependency: `pytest>=8`).
- Day API: `https://barrouxchant.com/api/hours/YYYY-MM-DD.json` returns `{hour: https mp3 url}`; an empty day returns `{}` with HTTP 200.
- Canonical hours, in order: `lauds prime terce sext none vespers compline`. The key `unknown` is never published.
- Audio archive starts at year 2017 (`FIRST_YEAR = 2017`); never query a date after the day being built.
- Ordo sources: monthly `https://propria.org/calendar/liturgical-calendar-YYYY-MM/` (2017-01 to 2018-11), annual `https://propria.org/archived-YYYY/` (2019 onward; the current year lives at `https://propria.org/ordo-YYYY/`). Pages are HTML tables: date, weekday, Mass name, class, colour; rows with a blank date are alternates and are ignored.
- Enclosures link to the original `cdn.barrouxchant.com` URLs. No audio is downloaded, mirrored or re-encoded.
- Neumz (`app.neumz.com`) is patron-gated and is never scraped or used.
- Feed window is 7 days (`WINDOW_DAYS = 7`), stateless and deterministic given the committed index.
- Channel carries `itunes:block yes` (private feed). Never submit it to a public directory.
- Episode `guid` is `barroux-daily:<YYYY-MM-DD>:<hour>`, `isPermaLink="false"`.
- `pubDate` for day D, hour index i (0-based) is D 00:0(i+1) in `FEED_TZ`.
- Every HTTP request sends `User-Agent: barroux-daily/0.1 (personal podcast feed)`; ordo scraping sleeps 1 second between requests.
- Env config: `FEED_TZ` (default `America/New_York`), `FEED_BASE_URL` (default `http://localhost:8000`), `OUT_DIR` (default `public`), `ORDO_INDEX` (default `data/ordo_index.json`).

## Review Focus

- A Sunday displaced by a feast: the ferias after it must not collide with the ferias of the previous week (same key twice in one year would pull the wrong week's chant). They get a `+n` week suffix instead.
- Today is not in the index (new ordo year not published yet, or the index file is missing): fall back to same month/day, say so in the description, and print a warning. Never crash, never silently pretend it matched liturgically.
- Site outage or empty archive: an HTTP 500 must fail the build, and zero episodes must refuse to publish. Either way the previously deployed feed stays live.
- A listed mp3 that 404s on the CDN: that episode is dropped, not shipped as a broken enclosure.
- Local midnight: "today" is computed in `FEED_TZ`, not UTC, so a build at 03:00 UTC is still yesterday in New York.

---

### Task 1: Project scaffold and day API client

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/barroux_daily/__init__.py`
- Create: `src/barroux_daily/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `fetch_day(d: date, get: Callable[[str], bytes] = http_get) -> dict[str, str]`: hour name to https mp3 URL, `{}` for an empty or 404 day, raises on other HTTP errors.
  - `head_length(url: str) -> int | None`: `Content-Length` (0 if header absent), `None` on HTTP 404, raises on other errors.
  - `http_get(url: str) -> bytes`, `USER_AGENT: str`.

- [ ] **Step 1: Scaffold the project**

The repo directory already holds `docs/` and `tests/fixtures/` (three real ordo pages captured 2026-10-15).

```bash
cd ~/code/barroux-daily
git init
python3 -m venv .venv
```

`pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "barroux-daily"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

`.gitignore`:

```
.venv/
__pycache__/
*.egg-info/
public/
```

`src/barroux_daily/__init__.py` is an empty file.

```bash
.venv/bin/pip install -e '.[dev]'
```

- [ ] **Step 2: Write the failing tests**

`tests/test_api.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_api.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'barroux_daily.api'`.

- [ ] **Step 4: Write the implementation**

`src/barroux_daily/api.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_api.py -v`
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore src tests docs
git commit -m "feat: scaffold project and barrouxchant day API client"
```

---

### Task 2: Parse the propria.org ordo pages into dated rows

**Files:**
- Create: `src/barroux_daily/ordo.py`
- Test: `tests/test_ordo.py`
- Fixtures (already present): `tests/fixtures/ordo-2018-10.html` (monthly page), `tests/fixtures/ordo-2019.html` (annual page, 2018-12-01 to 2019-12-01), `tests/fixtures/ordo-2026.html` (annual page, 2025-11-30 to 2026-11-30). Captured with `curl -sL https://propria.org/calendar/liturgical-calendar-2018-10/`, `.../archived-2019/`, `.../ordo-2026/`.

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `WEEKDAYS: tuple[str, ...]` (Monday first).
  - `@dataclass(frozen=True) Row(day: int, weekday: str, name: str)` where `name` is the first celebration listed in the Mass cell, as plain text (e.g. `"St. Teresa of Jesus, Virgin & Doctor"`, `"Feria"`).
  - `parse_rows(html: str) -> list[Row]`: one row per dated table row, in page order.
  - `assign_dates(rows: list[Row], starts: Sequence[tuple[int, int]]) -> dict[date, Row]`: tries each `(year, month)` start until every row's weekday matches its computed date; raises `ValueError` if none do.

- [ ] **Step 1: Write the failing tests**

`tests/test_ordo.py`:

```python
from datetime import date
from pathlib import Path

import pytest

from barroux_daily.ordo import Row, assign_dates, parse_rows

FIX = Path(__file__).parent / "fixtures"


def page(name):
    return (FIX / name).read_text(encoding="utf-8", errors="replace")


def test_monthly_page_gives_one_row_per_day():
    rows = parse_rows(page("ordo-2018-10.html"))
    assert [r.day for r in rows] == list(range(1, 32))
    by_day = {r.day: r for r in rows}
    assert by_day[15] == Row(15, "Monday", "St. Teresa of Avila, Virgin")
    assert by_day[14].name == "Twenty-First Sunday after Pentecost"


def test_annual_page_skips_alternate_rows():
    rows = parse_rows(page("ordo-2026.html"))
    assert len(rows) == 366
    assert rows[0].name.startswith("First Sunday of Advent")


def test_headers_and_blank_date_rows_are_ignored():
    html = (
        "<table><tr><td>Date</td><td>Day</td><td>The Mass</td></tr>"
        "<tr><td>3</td><td>Tuesday</td><td>St. Hedwig<em>, Widow</em><br>(or: X)</td><td>3</td></tr>"
        "<tr><td>&nbsp;</td><td>&nbsp;</td><td>in Carmelite churches: Y</td></tr></table>"
    )
    assert parse_rows(html) == [Row(3, "Tuesday", "St. Hedwig, Widow")]


def test_assign_dates_for_a_monthly_page():
    dated = assign_dates(parse_rows(page("ordo-2018-10.html")), [(2018, 10)])
    assert dated[date(2018, 10, 15)].name == "St. Teresa of Avila, Virgin"
    assert len(dated) == 31


def test_assign_dates_infers_the_start_month_of_an_annual_page():
    dated = assign_dates(parse_rows(page("ordo-2026.html")), [(2025, 11), (2025, 12)])
    assert min(dated) == date(2025, 11, 30)
    assert max(dated) == date(2026, 11, 30)
    assert dated[date(2026, 10, 15)].name == "St. Teresa of Jesus, Virgin & Doctor"
    assert dated[date(2026, 10, 18)].name == "Twenty-First Sunday after Pentecost"
    assert dated[date(2026, 10, 21)].name == "Feria"


def test_assign_dates_tries_the_next_candidate_start():
    dated = assign_dates(parse_rows(page("ordo-2019.html")), [(2018, 11), (2018, 12)])
    assert min(dated) == date(2018, 12, 1)


def test_wrong_start_month_raises():
    with pytest.raises(ValueError, match="weekday"):
        assign_dates(parse_rows(page("ordo-2018-10.html")), [(2018, 9)])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_ordo.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'barroux_daily.ordo'`.

- [ ] **Step 3: Write the implementation**

`src/barroux_daily/ordo.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from typing import Sequence

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


@dataclass(frozen=True)
class Row:
    day: int
    weekday: str
    name: str  # first celebration in the Mass cell, plain text


class _Table(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append("\n")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_rows(html: str) -> list[Row]:
    table = _Table()
    table.feed(html)
    rows = []
    for cells in table.rows:
        if len(cells) < 3:
            continue
        day, weekday = cells[0].strip(), cells[1].strip()
        if not day.isdigit() or weekday not in WEEKDAYS:
            continue  # header row, or an alternate celebration with a blank date
        name = " ".join(cells[2].split("\n")[0].split())
        rows.append(Row(int(day), weekday, name))
    return rows


def _walk(rows: Sequence[Row], year: int, month: int) -> dict[date, Row]:
    dated: dict[date, Row] = {}
    prev: int | None = None
    for row in rows:
        if prev is not None and row.day == 1 and prev != 1:
            month += 1
            if month == 13:
                year, month = year + 1, 1
        d = date(year, month, row.day)  # ValueError if the day does not exist
        if WEEKDAYS[d.weekday()] != row.weekday:
            raise ValueError(f"weekday mismatch at {d}: page says {row.weekday}")
        dated[d] = row
        prev = row.day
    return dated


def assign_dates(rows: Sequence[Row], starts: Sequence[tuple[int, int]]) -> dict[date, Row]:
    """Date each row. Tries each (year, month) start until every weekday agrees."""
    last: ValueError | None = None
    for year, month in starts:
        try:
            return _walk(rows, year, month)
        except ValueError as err:
            last = err
    raise ValueError(f"weekday check failed for every start month: {last}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_ordo.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/barroux_daily/ordo.py tests/test_ordo.py tests/fixtures
git commit -m "feat: parse propria.org ordo tables into dated rows"
```

---

### Task 3: Liturgical keys and the date index

**Files:**
- Create: `src/barroux_daily/liturgy.py`
- Test: `tests/test_liturgy.py`

**Interfaces:**
- Consumes: `Row`, `assign_dates`, `parse_rows` from Task 2.
- Produces:
  - `ALIASES: dict[str, str]` (normalized-name variants mapped to one canonical key; starts with `"teresa of avila" -> "teresa of jesus"`).
  - `norm(name: str) -> str`.
  - `@dataclass(frozen=True) Celebration(key: str, name: str)`; `key` identifies the liturgical day across years, `name` is for display.
  - `class Index` with `Index(entries: dict[date, Celebration])`, `celebration(d: date) -> Celebration | None`, `dates_for(key: str) -> list[date]` (newest first, `[]` if unknown), `span() -> tuple[date, date]`, `lonely_keys() -> list[str]` (non-feria keys seen on only one date), `__len__`, `save(path)`, `Index.load(path) -> Index`.
  - `celebrations(rows: dict[date, Row]) -> Index`.

- [ ] **Step 1: Write the failing tests**

`tests/test_liturgy.py`:

```python
from datetime import date, timedelta
from pathlib import Path

from barroux_daily.liturgy import Celebration, Index, celebrations, norm
from barroux_daily.ordo import WEEKDAYS, Row, assign_dates, parse_rows

FIX = Path(__file__).parent / "fixtures"


def dated(name, starts):
    html = (FIX / name).read_text(encoding="utf-8", errors="replace")
    return assign_dates(parse_rows(html), starts)


def week(start, names):
    """Consecutive days from start, one Row per name."""
    rows = {}
    for i, name in enumerate(names):
        d = start + timedelta(days=i)
        rows[d] = Row(d.day, WEEKDAYS[d.weekday()], name)
    return rows


def test_norm_strips_titles_ranks_punctuation_and_aliases_spelling_drift():
    assert norm("St. Teresa of Avila, Virgin") == "teresa of jesus"
    assert norm("St. Teresa of Jesus, Virgin & Doctor") == "teresa of jesus"
    assert norm("Twenty-First Sunday after Pentecost") == "twenty first sunday after pentecost"
    assert norm("First Sunday of Advent (Preface of Advent)") == "first sunday of advent"
    assert norm("Ss Ursula & Companions") == "ursula companions"


def test_feria_key_is_anchored_to_the_preceding_temporal_sunday():
    rows = week(date(2026, 10, 11), ["Twentieth Sunday after Pentecost", "Feria", "St. Hedwig, Widow", "Feria"])
    idx = celebrations(rows)
    assert idx.celebration(date(2026, 10, 12)).key == "feria|twentieth sunday after pentecost|monday"
    assert idx.celebration(date(2026, 10, 12)).name == "Monday after Twentieth Sunday after Pentecost"
    assert idx.celebration(date(2026, 10, 13)).key == "hedwig"
    assert idx.celebration(date(2026, 10, 14)).key == "feria|twentieth sunday after pentecost|wednesday"


def test_displaced_sunday_gets_a_week_suffix_so_keys_stay_unique_within_a_year():
    names = ["Twentieth Sunday after Pentecost", "Feria"] + ["Feria"] * 5 + ["Dedication of a Basilica", "Feria"]
    idx = celebrations(week(date(2026, 10, 11), names))
    first_monday = idx.celebration(date(2026, 10, 12)).key
    second_monday = idx.celebration(date(2026, 10, 19)).key
    assert first_monday == "feria|twentieth sunday after pentecost|monday"
    assert second_monday == "feria|twentieth sunday after pentecost+1|monday"
    assert first_monday != second_monday


def test_feria_with_no_anchor_still_gets_a_unique_key():
    idx = celebrations(week(date(2026, 10, 12), ["Feria"]))
    assert idx.celebration(date(2026, 10, 12)).key == "feria|2026-10-12"


def test_index_lookup_newest_first_and_unknown_cases():
    a, b, c = date(2024, 5, 1), date(2025, 5, 1), date(2026, 5, 1)
    idx = Index({a: Celebration("k", "K"), b: Celebration("k", "K"), c: Celebration("z", "Z")})
    assert idx.dates_for("k") == [b, a]
    assert idx.dates_for("nope") == []
    assert idx.celebration(date(2000, 1, 1)) is None
    assert idx.span() == (a, c)
    assert idx.lonely_keys() == ["z"]
    assert len(idx) == 3


def test_index_json_round_trip(tmp_path):
    idx = Index({date(2026, 10, 15): Celebration("teresa of jesus", "St. Teresa of Jesus")})
    path = tmp_path / "sub" / "idx.json"
    idx.save(path)
    again = Index.load(path)
    assert again.celebration(date(2026, 10, 15)) == Celebration("teresa of jesus", "St. Teresa of Jesus")


def test_real_ordo_pages_match_the_same_celebration_across_years():
    rows = {}
    rows.update(dated("ordo-2018-10.html", [(2018, 10)]))
    rows.update(dated("ordo-2019.html", [(2018, 11), (2018, 12)]))
    rows.update(dated("ordo-2026.html", [(2025, 11), (2025, 12)]))
    idx = celebrations(rows)

    teresa = idx.celebration(date(2026, 10, 15))
    assert teresa.key == "teresa of jesus"
    assert teresa.name == "St. Teresa of Jesus, Virgin & Doctor"
    assert idx.dates_for(teresa.key) == [date(2026, 10, 15), date(2019, 10, 15), date(2018, 10, 15)]

    sunday = idx.celebration(date(2026, 10, 18))
    assert sunday.key == idx.celebration(date(2018, 10, 14)).key == "twenty first sunday after pentecost"

    # A feria lands on the same liturgical day even when the calendar date differs.
    feria = idx.celebration(date(2026, 10, 21))
    assert feria.key == "feria|twenty first sunday after pentecost|wednesday"
    assert idx.dates_for(feria.key) == [date(2026, 10, 21), date(2019, 11, 6)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_liturgy.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'barroux_daily.liturgy'`.

- [ ] **Step 3: Write the implementation**

`src/barroux_daily/liturgy.py`:

```python
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .ordo import Row

# Add a pair here when the same feast is spelled differently in different years.
# `python -m barroux_daily.ordo_index` prints the keys that appear on only one date;
# a pair of lookalikes in that list means an alias is missing.
ALIASES = {
    "teresa of avila": "teresa of jesus",
}

_TEMPORAL_SUNDAY = re.compile(r"\bsunday\b|pentecost|easter", re.I)
_TITLES = re.compile(r"\b(st|saint|ss|blessed|bl)\b\.?")


def norm(name: str) -> str:
    """Stable identity for a celebration: lowercase, no titles, no rank, no punctuation."""
    s = name.split(",")[0].lower()
    s = re.sub(r"\(.*", "", s)
    s = _TITLES.sub(" ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = " ".join(s.split())
    return ALIASES.get(s, s)


def _title(name: str) -> str:
    return re.sub(r"\s*\(.*", "", name).strip()


@dataclass(frozen=True)
class Celebration:
    key: str  # identifies the liturgical day across years
    name: str  # for display


class Index:
    def __init__(self, entries: dict[date, Celebration]) -> None:
        self._entries = dict(entries)
        self._by_key: dict[str, list[date]] = {}
        for d in sorted(self._entries, reverse=True):
            self._by_key.setdefault(self._entries[d].key, []).append(d)

    def __len__(self) -> int:
        return len(self._entries)

    def celebration(self, d: date) -> Celebration | None:
        return self._entries.get(d)

    def dates_for(self, key: str) -> list[date]:
        return list(self._by_key.get(key, []))

    def span(self) -> tuple[date, date]:
        days = sorted(self._entries)
        return days[0], days[-1]

    def lonely_keys(self) -> list[str]:
        return sorted(
            k for k, ds in self._by_key.items() if len(ds) == 1 and not k.startswith("feria|")
        )

    def save(self, path: str | Path) -> None:
        data = {d.isoformat(): [c.key, c.name] for d, c in sorted(self._entries.items())}
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Index":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls({date.fromisoformat(k): Celebration(*v) for k, v in data.items()})


def celebrations(rows: dict[date, Row]) -> Index:
    """Key every date. Run on the merged rows of all pages so ferias can see their Sunday."""
    entries: dict[date, Celebration] = {}
    anchor: str | None = None
    anchor_name = ""
    displaced = 0  # temporal Sundays displaced by a feast since the anchor
    for d in sorted(rows):
        row = rows[d]
        if row.weekday == "Sunday":
            if _TEMPORAL_SUNDAY.search(row.name):
                anchor, anchor_name, displaced = norm(row.name), _title(row.name), 0
            else:
                displaced += 1
        if row.name.lower().startswith("feria"):
            if anchor is None:
                key, name = f"feria|{d.isoformat()}", "Feria"
            else:
                tag = anchor if displaced == 0 else f"{anchor}+{displaced}"
                key = f"feria|{tag}|{row.weekday.lower()}"
                name = f"{row.weekday} after {anchor_name}"
                if displaced:
                    name += f" (+{displaced} wk)"
        else:
            key, name = norm(row.name), _title(row.name)
        entries[d] = Celebration(key, name)
    return Index(entries)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_liturgy.py -v`
Expected: 7 passed. If `test_real_ordo_pages_match_the_same_celebration_across_years` fails on a date list, print `idx.dates_for(...)` and compare to the fixture pages before touching any code: the dates in the test were verified against the three fixtures on 2026-10-15.

- [ ] **Step 5: Commit**

```bash
git add src/barroux_daily/liturgy.py tests/test_liturgy.py
git commit -m "feat: liturgical keys and date index from ordo rows"
```

---

### Task 4: Build and commit the ordo index from the live site

**Files:**
- Create: `src/barroux_daily/ordo_index.py`
- Create: `data/ordo_index.json` (generated, committed)
- Test: `tests/test_ordo_index.py`

**Interfaces:**
- Consumes: `parse_rows`, `assign_dates` (Task 2); `celebrations`, `Index` (Task 3); `http_get` (Task 1).
- Produces:
  - `@dataclass(frozen=True) Page(urls: tuple[str, ...], starts: tuple[tuple[int, int], ...], required: bool = True)`.
  - `default_pages(this_year: int) -> list[Page]`.
  - `build_index(pages: Sequence[Page], fetch: Callable[[str], str]) -> Index`: for each page, tries its URLs in order (an HTTP 404 or a page with zero rows moves on to the next URL); a `required` page with no usable URL raises `RuntimeError`, an optional one is skipped. Later pages override earlier ones on overlapping dates.
  - `main() -> None` (`python -m barroux_daily.ordo_index`) writes `$ORDO_INDEX` (default `data/ordo_index.json`).

- [ ] **Step 1: Write the failing tests**

`tests/test_ordo_index.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_ordo_index.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'barroux_daily.ordo_index'`.

- [ ] **Step 3: Write the implementation**

`src/barroux_daily/ordo_index.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_ordo_index.py -v`
Expected: 4 passed.

- [ ] **Step 5: Generate the real index from the live site**

Run (about 35 seconds, 32 polite requests):
```bash
.venv/bin/python -m barroux_daily.ordo_index
```
Expected: `wrote data/ordo_index.json: ~3,600 days, 2017-01-01 to 2026-11-30` (the 2027 page does not exist yet and is skipped). Then a list of "lonely" keys: mostly one-off events, but any *pair* of lookalike names (same saint, different spelling) means an alias is missing from `ALIASES` in `liturgy.py`. Add aliases, rerun, until the obvious pairs are gone. Do not chase every entry; the aim is the common feasts.

Spot check:
```bash
.venv/bin/python - <<'E'
from datetime import date
from barroux_daily.liturgy import Index
idx = Index.load("data/ordo_index.json")
c = idx.celebration(date(2026, 10, 15))
print(c)
print([d.isoformat() for d in idx.dates_for(c.key)])
E
```
Expected: `Celebration(key='teresa of jesus', name='St. Teresa of Jesus, Virgin & Doctor')` and Oct 15 of most years 2017 to 2025 (a year is absent if Oct 15 fell on a Sunday and displaced her).

- [ ] **Step 6: Commit**

```bash
git add src/barroux_daily/ordo_index.py tests/test_ordo_index.py src/barroux_daily/liturgy.py data/ordo_index.json
git commit -m "feat: build and commit the liturgical date index from propria.org"
```

---

### Task 5: Episode selection by liturgical day

**Files:**
- Create: `src/barroux_daily/episodes.py`
- Test: `tests/test_episodes.py`

**Interfaces:**
- Consumes: `fetch_day(d: date) -> dict[str, str]` (Task 1, injected as `get_day`); `Index`, `Celebration` (Task 3).
- Produces:
  - `HOURS: tuple[str, ...]` = `("lauds","prime","terce","sext","none","vespers","compline")`
  - `HOUR_LABELS: dict[str, str]` (display names; `none` maps to `"Nones"`)
  - `FIRST_YEAR = 2017`
  - `@dataclass(frozen=True) Episode(day: date, hour: str, recorded: date, url: str, celebration: str | None)`: `day` is the day the episode is published for, `recorded` the date of the recording, `celebration` the display name from the ordo (`None` when matched by calendar date).
  - `candidate_dates(day: date, index: Index | None, first_year: int = FIRST_YEAR) -> list[date]`: newest first, never after `day`, never before `first_year`. Same-key dates if `day` is in the index, otherwise same month/day in each earlier year (Feb 29 skips non-leap years).
  - `episodes_for(day: date, get_day=fetch_day, index: Index | None = None, first_year: int = FIRST_YEAR) -> list[Episode]` in canonical hour order.

- [ ] **Step 1: Write the failing tests**

`tests/test_episodes.py`:

```python
from datetime import date

from barroux_daily.episodes import FIRST_YEAR, HOURS, Episode, candidate_dates, episodes_for
from barroux_daily.liturgy import Celebration, Index


def url(d, hour):
    return f"https://cdn.barrouxchant.com/{d.isoformat()}-{hour}.mp3"


def archive(spec):
    """spec: {date: [hours]} -> (get_day, calls); calls records every date queried."""
    calls = []

    def get_day(d):
        calls.append(d)
        return {h: url(d, h) for h in spec.get(d, [])}

    return get_day, calls


TERESA = Celebration("teresa", "St. Teresa of Jesus")
SUNDAY = Celebration("sunday21", "Twenty-First Sunday after Pentecost")


def teresa_index(*dates):
    return Index({d: TERESA for d in dates} | {date(2025, 10, 16): Celebration("hedwig", "St. Hedwig")})


def test_liturgical_match_picks_newest_recording_per_hour_in_canonical_order():
    d26, d25, d24 = date(2026, 10, 15), date(2025, 10, 15), date(2024, 10, 15)
    get_day, _ = archive({d25: ["vespers", "lauds"], d24: ["lauds", "prime"]})
    eps = episodes_for(d26, get_day, teresa_index(d26, d25, d24))
    assert [(e.hour, e.recorded) for e in eps] == [("lauds", d25), ("prime", d24), ("vespers", d25)]
    assert eps[0] == Episode(d26, "lauds", d25, url(d25, "lauds"), "St. Teresa of Jesus")


def test_recordings_from_a_different_calendar_date_are_used_when_the_celebration_matches():
    today, moved = date(2026, 10, 18), date(2019, 11, 3)
    get_day, calls = archive({moved: ["lauds"]})
    idx = Index({today: SUNDAY, moved: SUNDAY, date(2019, 10, 20): Celebration("other", "Other")})
    (ep,) = episodes_for(today, get_day, idx)
    assert ep.recorded == moved
    assert date(2019, 10, 20) not in calls  # same weekday-ish neighbours are never queried


def test_the_days_own_recording_wins_over_the_archive():
    d26, d25 = date(2026, 10, 15), date(2025, 10, 15)
    get_day, _ = archive({d26: ["lauds"], d25: ["lauds"]})
    (ep,) = episodes_for(d26, get_day, teresa_index(d26, d25))
    assert ep.recorded == d26


def test_unknown_is_never_published_and_the_hour_falls_back_to_an_earlier_year():
    d26, d25, d24 = date(2026, 10, 15), date(2025, 10, 15), date(2024, 10, 15)
    get_day, _ = archive({d25: ["unknown"], d24: ["compline"]})
    eps = episodes_for(d26, get_day, teresa_index(d26, d25, d24))
    assert [(e.hour, e.recorded) for e in eps] == [("compline", d24)]


def test_never_queries_the_future_or_before_first_year():
    day = date(2025, 10, 15)
    idx = Index({day: TERESA, date(2026, 10, 15): TERESA, date(2016, 10, 15): TERESA, date(2017, 10, 15): TERESA})
    assert candidate_dates(day, idx) == [day, date(2017, 10, 15)]


def test_stops_as_soon_as_every_hour_is_found():
    d26, d25, d24 = date(2026, 10, 15), date(2025, 10, 15), date(2024, 10, 15)
    get_day, calls = archive({d25: list(HOURS)})
    eps = episodes_for(d26, get_day, teresa_index(d26, d25, d24))
    assert len(eps) == 7
    assert calls == [d26, d25]


def test_nothing_anywhere_gives_empty_list():
    get_day, _ = archive({})
    assert episodes_for(date(2026, 10, 15), get_day, teresa_index(date(2026, 10, 15))) == []


def test_day_missing_from_the_index_falls_back_to_the_calendar_date_and_has_no_celebration():
    day = date(2027, 3, 4)
    older = date(2025, 3, 4)
    get_day, calls = archive({older: ["lauds"]})
    (ep,) = episodes_for(day, get_day, Index({date(2026, 10, 15): TERESA}))
    assert ep.recorded == older
    assert ep.celebration is None
    assert calls[0] == day and calls[1] == date(2026, 3, 4)


def test_no_index_at_all_also_falls_back_and_feb_29_skips_non_leap_years():
    get_day, calls = archive({date(2020, 2, 29): ["lauds"]})
    eps = episodes_for(date(2024, 2, 29), get_day, None)
    assert [(e.hour, e.recorded) for e in eps] == [("lauds", date(2020, 2, 29))]
    assert {d.year for d in calls} == {2024, 2020}
    assert all((d.month, d.day) == (2, 29) for d in calls)
    assert min(candidate_dates(date(2025, 10, 15), None)).year == FIRST_YEAR
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_episodes.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'barroux_daily.episodes'`.

- [ ] **Step 3: Write the implementation**

`src/barroux_daily/episodes.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from .api import fetch_day
from .liturgy import Index

HOURS = ("lauds", "prime", "terce", "sext", "none", "vespers", "compline")
HOUR_LABELS = {
    "lauds": "Lauds",
    "prime": "Prime",
    "terce": "Terce",
    "sext": "Sext",
    "none": "Nones",
    "vespers": "Vespers",
    "compline": "Compline",
}
FIRST_YEAR = 2017


@dataclass(frozen=True)
class Episode:
    day: date  # the day this episode is published for
    hour: str
    recorded: date  # when the monks recorded it
    url: str
    celebration: str | None  # ordo name for `day`; None when matched by calendar date only


def candidate_dates(day: date, index: Index | None, first_year: int = FIRST_YEAR) -> list[date]:
    """Dates whose recordings could stand in for `day`, newest first."""
    cel = index.celebration(day) if index is not None else None
    if cel is not None:
        return [d for d in index.dates_for(cel.key) if d <= day and d.year >= first_year]
    dates = []
    for year in range(day.year, first_year - 1, -1):
        try:
            dates.append(date(year, day.month, day.day))
        except ValueError:  # Feb 29 in a non-leap year
            pass
    return dates


def episodes_for(
    day: date,
    get_day: Callable[[date], dict[str, str]] = fetch_day,
    index: Index | None = None,
    first_year: int = FIRST_YEAR,
) -> list[Episode]:
    cel = index.celebration(day) if index is not None else None
    name = cel.name if cel is not None else None
    found: dict[str, Episode] = {}
    for source in candidate_dates(day, index, first_year):
        if len(found) == len(HOURS):
            break
        for hour, url in get_day(source).items():
            if hour in HOURS and hour not in found:
                found[hour] = Episode(day, hour, source, url, name)
    return [found[h] for h in HOURS if h in found]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_episodes.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/barroux_daily/episodes.py tests/test_episodes.py
git commit -m "feat: pick the newest recording per hour for the same liturgical day"
```

---

### Task 6: RSS feed rendering

**Files:**
- Create: `src/barroux_daily/feed.py`
- Test: `tests/test_feed.py`

**Interfaces:**
- Consumes: `Episode`, `HOURS`, `HOUR_LABELS` from Task 5.
- Produces:
  - `pub_date(ep: Episode, zone: ZoneInfo) -> datetime`
  - `render_feed(items: list[tuple[Episode, int]], tz: str, base_url: str) -> bytes`: each item is an episode plus its enclosure byte length. UTF-8 XML, items sorted newest first. Title is `"<Hour> · <celebration>"`, or `"<Hour> · <Month> <day>"` when `celebration` is `None`.

- [ ] **Step 1: Write the failing tests**

`tests/test_feed.py`:

```python
import xml.etree.ElementTree as ET
from datetime import date
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from barroux_daily.episodes import Episode
from barroux_daily.feed import pub_date, render_feed

NS = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}
NY = "America/New_York"


def ep(day, hour, recorded=None, url=None, celebration="St. Teresa of Jesus, Virgin & Doctor"):
    recorded = recorded or date(2025, day.month, day.day)
    url = url or f"https://cdn.barrouxchant.com/{recorded.isoformat()}-{hour}.mp3"
    return Episode(day, hour, recorded, url, celebration)


def parse(items):
    root = ET.fromstring(render_feed(items, NY, "https://example.github.io/barroux-daily"))
    return root.find("channel")


def test_channel_metadata_and_private_block():
    ch = parse([(ep(date(2026, 10, 15), "lauds"), 100)])
    assert ch.findtext("title") == "Barroux Chant: Today's Office"
    assert ch.findtext("language") == "la"
    assert ch.findtext("itunes:block", namespaces=NS) == "yes"
    assert ch.findtext("itunes:explicit", namespaces=NS) == "no"
    assert ch.find("itunes:image", NS).get("href").startswith("http")


def test_item_fields_for_a_liturgically_matched_episode():
    d = date(2026, 10, 15)
    ch = parse([(ep(d, "none"), 46082089)])
    (item,) = ch.findall("item")
    assert item.findtext("title") == "Nones · St. Teresa of Jesus, Virgin & Doctor"
    description = item.findtext("description")
    assert "recorded October 15, 2025" in description
    assert "calendar date" not in description
    guid = item.find("guid")
    assert guid.text == "barroux-daily:2026-10-15:none"
    assert guid.get("isPermaLink") == "false"
    enc = item.find("enclosure")
    assert enc.get("url") == "https://cdn.barrouxchant.com/2025-10-15-none.mp3"
    assert enc.get("length") == "46082089"
    assert enc.get("type") == "audio/mpeg"


def test_calendar_matched_episode_says_so_and_titles_by_date():
    d = date(2027, 3, 4)
    ch = parse([(ep(d, "lauds", celebration=None), 5)])
    item = ch.find("item")
    assert item.findtext("title") == "Lauds · March 4"
    assert "matched by calendar date" in item.findtext("description")


def test_pub_date_is_local_midnight_plus_hour_index():
    zone = ZoneInfo(NY)
    d = date(2025, 10, 15)  # EDT, UTC-4
    assert pub_date(ep(d, "lauds"), zone).isoformat() == "2025-10-15T00:01:00-04:00"
    assert pub_date(ep(d, "compline"), zone).isoformat() == "2025-10-15T00:07:00-04:00"
    winter = date(2025, 12, 15)  # EST, UTC-5
    assert pub_date(ep(winter, "lauds"), zone).isoformat() == "2025-12-15T00:01:00-05:00"


def test_items_are_newest_first_and_dates_are_rfc2822():
    d1, d2 = date(2026, 10, 14), date(2026, 10, 15)
    items = [(ep(d1, "compline"), 1), (ep(d2, "lauds"), 1), (ep(d2, "prime"), 1), (ep(d1, "lauds"), 1)]
    ch = parse(items)
    guids = [i.findtext("guid") for i in ch.findall("item")]
    assert guids == [
        "barroux-daily:2026-10-15:prime",
        "barroux-daily:2026-10-15:lauds",
        "barroux-daily:2026-10-14:compline",
        "barroux-daily:2026-10-14:lauds",
    ]
    stamp = ch.find("item").findtext("pubDate")
    assert parsedate_to_datetime(stamp).isoformat() == "2026-10-15T00:02:00-04:00"


def test_urls_with_ampersands_survive_xml_escaping():
    url = "https://cdn.barrouxchant.com/x.mp3?a=1&b=2"
    ch = parse([(ep(date(2026, 10, 15), "lauds", url=url), 5)])
    assert ch.find("item/enclosure").get("url") == url
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_feed.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'barroux_daily.feed'`.

- [ ] **Step 3: Write the implementation**

`src/barroux_daily/feed.py`:

```python
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, time
from email.utils import format_datetime
from zoneinfo import ZoneInfo

from .episodes import HOUR_LABELS, HOURS, Episode

ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ET.register_namespace("itunes", ITUNES)

IMAGE = "http://barrouxchant.com/resources/podcast-logo-large.jpg"
AUTHOR = "Abbaye Sainte-Madeleine du Barroux"


def _q(tag: str) -> str:
    return f"{{{ITUNES}}}{tag}"


def _text(parent: ET.Element, tag: str, value: str, **attrs: str) -> ET.Element:
    el = ET.SubElement(parent, tag, attrs)
    el.text = value
    return el


def pub_date(ep: Episode, zone: ZoneInfo) -> datetime:
    """Local midnight + (hour index + 1) minutes, so hours sort in liturgical order."""
    return datetime.combine(ep.day, time(0, HOURS.index(ep.hour) + 1), tzinfo=zone)


def _title(ep: Episode) -> str:
    label = HOUR_LABELS[ep.hour]
    return f"{label} · {ep.celebration}" if ep.celebration else f"{label} · {ep.day:%B} {ep.day.day}"


def _description(ep: Episode) -> str:
    text = (
        f"{HOUR_LABELS[ep.hour]}, recorded {ep.recorded:%B} {ep.recorded.day}, {ep.recorded.year}. "
        "Chanted by the monks of Sainte-Madeleine du Barroux."
    )
    if ep.celebration is None:
        text += " Matched by calendar date (liturgical calendar unavailable), so movable feasts may differ."
    return text


def render_feed(items: list[tuple[Episode, int]], tz: str, base_url: str) -> bytes:
    zone = ZoneInfo(tz)
    rss = ET.Element("rss", {"version": "2.0"})
    ch = ET.SubElement(rss, "channel")
    _text(ch, "title", "Barroux Chant: Today's Office")
    _text(ch, "link", base_url)
    _text(
        ch,
        "description",
        "The Divine Office chanted by the monks of Le Barroux, for today's liturgical day, "
        "assembled from the barrouxchant.com archive. Private feed.",
    )
    _text(ch, "language", "la")
    _text(ch, _q("author"), AUTHOR)
    _text(ch, _q("explicit"), "no")
    _text(ch, _q("type"), "episodic")
    _text(ch, _q("block"), "yes")
    ET.SubElement(ch, _q("image"), {"href": IMAGE})
    cat = ET.SubElement(ch, _q("category"), {"text": "Religion & Spirituality"})
    ET.SubElement(cat, _q("category"), {"text": "Christianity"})

    for ep, length in sorted(items, key=lambda it: pub_date(it[0], zone), reverse=True):
        item = ET.SubElement(ch, "item")
        _text(item, "title", _title(ep))
        _text(item, "description", _description(ep))
        _text(item, "guid", f"barroux-daily:{ep.day.isoformat()}:{ep.hour}", isPermaLink="false")
        _text(item, "pubDate", format_datetime(pub_date(ep, zone)))
        ET.SubElement(
            item,
            "enclosure",
            {"url": ep.url, "length": str(length), "type": "audio/mpeg"},
        )
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_feed.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/barroux_daily/feed.py tests/test_feed.py
git commit -m "feat: render RSS feed with itunes tags and ordered pubDates"
```

---

### Task 7: Build orchestration, CLI, and local-day handling

**Files:**
- Create: `src/barroux_daily/build.py`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: `fetch_day`, `head_length` (Task 1); `Index`, `Celebration` (Task 3); `episodes_for`, `Episode` (Task 5); `render_feed` (Task 6).
- Produces:
  - `WINDOW_DAYS = 7`
  - `local_today(tz: str, now_utc: datetime) -> date`
  - `build_feed(today: date, get_day, probe, tz: str, base_url: str, index: Index | None = None, window: int = WINDOW_DAYS) -> bytes`; raises `RuntimeError` ("... refusing to publish an empty feed") if no episodes survive.
  - `load_index(path: Path) -> Index | None`: `None` plus a warning on stderr if the file is missing.
  - `main() -> None` (`python -m barroux_daily.build`) writes `$OUT_DIR/feed.xml` and `$OUT_DIR/index.html`.

- [ ] **Step 1: Write the failing tests**

`tests/test_build.py`:

```python
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone

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
    xml = build_feed(date(2026, 10, 15), only_lauds, lambda u: 10, NY, BASE, window=2)
    assert guids(xml) == ["barroux-daily:2026-10-15:lauds", "barroux-daily:2026-10-14:lauds"]


def test_default_window_is_seven_days():
    xml = build_feed(date(2026, 10, 15), only_lauds, lambda u: 10, NY, BASE)
    assert len(guids(xml)) == build.WINDOW_DAYS == 7


def test_episode_whose_file_404s_is_dropped():
    def probe(url):
        return None if "2026-10-14" in url else 10

    xml = build_feed(date(2026, 10, 15), only_lauds, probe, NY, BASE, window=2)
    assert guids(xml) == ["barroux-daily:2026-10-15:lauds"]


def test_enclosure_length_comes_from_probe():
    xml = build_feed(date(2026, 10, 15), only_lauds, lambda u: 1234, NY, BASE, window=1)
    assert ET.fromstring(xml).find("channel/item/enclosure").get("length") == "1234"


def test_titles_use_the_index_celebration_name():
    idx = Index({date(2026, 10, 15): Celebration("teresa", "St. Teresa of Jesus")})
    xml = build_feed(date(2026, 10, 15), only_lauds, lambda u: 10, NY, BASE, index=idx, window=1)
    assert ET.fromstring(xml).findtext("channel/item/title") == "Lauds · St. Teresa of Jesus"


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
    build.main()
    assert (tmp_path / "feed.xml").read_bytes().startswith(b"<?xml")
    assert f"{BASE}/feed.xml" in (tmp_path / "index.html").read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_build.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'barroux_daily.build'`.

- [ ] **Step 3: Write the implementation**

`src/barroux_daily/build.py`:

```python
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
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/pytest -v`
Expected: all pass (api 8, ordo 7, liturgy 7, ordo_index 4, episodes 9, feed 6, build 10 = 51 passed).

- [ ] **Step 5: Smoke test against the live site**

Run:
```bash
OUT_DIR=/tmp/barroux-smoke FEED_BASE_URL=http://localhost:8000 .venv/bin/python -m barroux_daily.build
grep -o "<item>" /tmp/barroux-smoke/feed.xml | wc -l
grep -o "<title>[^<]*</title>" /tmp/barroux-smoke/feed.xml | head -9
grep -o "recorded [A-Za-z]* [0-9]*, [0-9]*" /tmp/barroux-smoke/feed.xml | head -9
```
Expected: `wrote /tmp/barroux-smoke/feed.xml for <today>`; roughly 30 to 49 items; today's titles read like `Lauds · St. Teresa of Jesus, Virgin & Doctor`; recording dates come from prior years' Oct 15 (2025, 2024, ...) for that celebration, and for a Sunday or feria they may fall in a different month. Takes under a minute. If it raises an HTTP error the site is down: retry later, do not "fix" it.

Then read today's and one Sunday's matches with your own eyes: you know the Office. If a match looks wrong (wrong saint, wrong week), add an alias to `ALIASES` in `liturgy.py`, rerun `python -m barroux_daily.ordo_index`, and rebuild.

- [ ] **Step 6: Commit**

```bash
git add src/barroux_daily/build.py tests/test_build.py
git commit -m "feat: build 7-day feed from the ordo index, refuse empty output, local-day handling"
```

---

### Task 8: Daily GitHub Actions deploy to Pages, monthly ordo refresh, README

**Files:**
- Create: `.github/workflows/daily.yml`
- Create: `.github/workflows/refresh-ordo.yml`
- Create: `README.md`

**Interfaces:**
- Consumes: `python -m barroux_daily.build` and `python -m barroux_daily.ordo_index` with their env vars (Tasks 4 and 7).
- Produces: the feed URL `https://<github-user>.github.io/barroux-daily/feed.xml`, and a monthly-refreshed `data/ordo_index.json`.

- [ ] **Step 1: Write the workflows**

`.github/workflows/daily.yml`:

```yaml
name: daily-feed

on:
  schedule:
    - cron: "17 6 * * *" # 06:17 UTC, after local midnight in the Americas and Europe
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e '.[dev]'
      - run: pytest -q
      - run: python -m barroux_daily.build
        env:
          FEED_TZ: America/New_York
          FEED_BASE_URL: https://${{ github.repository_owner }}.github.io/barroux-daily
      - uses: actions/upload-pages-artifact@v3
        with:
          path: public

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

A failed build (site outage, or the empty-feed guard) skips `deploy`, so the previous feed stays live.

`.github/workflows/refresh-ordo.yml`:

```yaml
name: refresh-ordo

on:
  schedule:
    - cron: "23 5 2 * *" # 2nd of each month; picks up next year's ordo when propria.org posts it
  workflow_dispatch:

permissions:
  contents: write

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e '.[dev]'
      - run: python -m barroux_daily.ordo_index
      - run: pytest -q
      - name: Commit if the index changed
        run: |
          if git diff --quiet data/ordo_index.json; then
            echo "ordo index unchanged"
          else
            git config user.name "github-actions"
            git config user.email "actions@users.noreply.github.com"
            git add data/ordo_index.json
            git commit -m "chore: refresh ordo index"
            git push
          fi
```

Pushes made with the default token do not trigger other workflows, so a refreshed index goes live at the next daily 06:17 UTC build (or run `daily-feed` by hand).

- [ ] **Step 2: Write the README**

`README.md`:

````markdown
# barroux-daily

A private podcast feed of today's Divine Office, chanted by the monks of Le Barroux,
for praying with. barrouxchant.com records the monks' stream but posts irregularly.
This takes today's liturgical day (from the propria.org ordo), finds the same
celebration in earlier years, and fills each hour from the newest recording that
has it. It rebuilds every day.

Audio is never copied: episodes stream from `cdn.barrouxchant.com`.

## Subscribe

Feed URL: `https://<github-user>.github.io/barroux-daily/feed.xml`

- Apple Podcasts: Library > ... > Follow a Show by URL
- Overcast / Pocket Casts / Castro / AntennaPod: add by URL
- Spotify: not supported. Spotify only takes public submissions, and these recordings
  belong to the abbey. Do not submit this feed publicly without their permission.

## How it matches

Saints and named days match by name (`St. Teresa of Jesus`, `Twenty-First Sunday after
Pentecost`). Ferias match as "weekday after Sunday X", so a Wednesday in Oct 2026 can be
filled from a Wednesday in November 2019. Each episode says when it was recorded.

The ordo is the Roman 1962 Mass calendar; Le Barroux is Benedictine, so on a few days
their Office may differ from the match. If a day looks off, add an alias in
`src/barroux_daily/liturgy.py` (`ALIASES`) and run `python -m barroux_daily.ordo_index`.

## Run locally

```bash
pip install -e '.[dev]'
pytest
python -m barroux_daily.ordo_index   # refresh data/ordo_index.json (~35 s)
python -m barroux_daily.build        # writes public/feed.xml
```

Config: `FEED_TZ` (default `America/New_York`), `FEED_BASE_URL`, `OUT_DIR`, `ORDO_INDEX`.
````

- [ ] **Step 3: Create the GitHub repo and enable Pages**

Stop here and confirm with Joe before running the next block: `gh repo create` publishes the code.

```bash
cd ~/code/barroux-daily
git branch -M main
git add .github README.md
git commit -m "ci: daily build and Pages deploy, monthly ordo refresh; add README"
gh repo create barroux-daily --public --source=. --remote=origin
gh api -X POST repos/{owner}/barroux-daily/pages -f build_type=workflow
git push -u origin main
```

Public is required for free Pages. The feed URL is only guessable by someone who knows the repo name, and `itunes:block yes` keeps it out of Apple's directory.

- [ ] **Step 4: Verify the deployed feed**

```bash
gh run watch
curl -s https://<github-user>.github.io/barroux-daily/feed.xml | head -c 600
curl -s https://<github-user>.github.io/barroux-daily/feed.xml | grep -c "<item>"
```
Expected: run succeeds; feed starts with `<?xml` and `<rss`; item count matches the smoke test. Add the feed URL to a podcast app and confirm one episode plays.

- [ ] **Step 5: Commit any fixes**

```bash
git add -A && git commit -m "fix: deploy adjustments" && git push
```
(Skip if nothing changed.)
