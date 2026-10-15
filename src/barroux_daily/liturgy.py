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
