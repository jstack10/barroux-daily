from __future__ import annotations

from dataclasses import dataclass
import sys
from datetime import date, timedelta
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
    """Date rows sequentially: the first from its day number, the rest as previous + 1 day."""
    dated: dict[date, Row] = {}
    d: date | None = None
    for row in rows:
        if d is None:
            try:
                d = date(year, month, row.day)
            except ValueError:
                raise ValueError(f"first row day {row.day} does not exist in {year}-{month:02d}") from None
        else:
            d += timedelta(days=1)
        if WEEKDAYS[d.weekday()] != row.weekday:
            raise ValueError(f"weekday mismatch at {d}: page says {row.weekday}")
        if d.day != row.day:
            print(
                f"warning: ordo page row says day {row.day} but calendar says {d} (weekday agrees)",
                file=sys.stderr,
            )
        dated[d] = row
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
