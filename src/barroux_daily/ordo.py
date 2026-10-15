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
