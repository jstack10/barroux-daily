from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .ordo import Row

# Add a pair here when the same celebration is spelled differently in different years.
# Keys are in `norm` form (accents folded, no titles, no leading "the", no "and").
# `python -m barroux_daily.ordo_index` prints the keys that appear on only one date and
# near-duplicate keys; a pair of lookalikes there means an alias is missing.
# Only alias days that are genuinely the same celebration.
ALIASES = {
    # temporal cycle
    "dominica resurrectionis": "easter sunday",
    "divine mercy sunday": "dominica in albis",  # Low Sunday
    "second sunday after easter": "good shepherd sunday",
    "first sunday of passiontide": "passion sunday",
    "second sunday of passiontide": "palm sunday",
    "holy thursday": "maundy thursday",
    "wednesday of holy week office of tenebrae": "wednesday of holy week",
    "good friday mass of the presanctified": "good friday",
    "good friday office mass of the presanctified": "good friday",
    "easter vigil mass": "holy saturday",
    "solemn easter vigil first mass of easter sunday": "holy saturday",
    "vigil of pentecost": "vigil mass of pentecost",
    "twenty fourth last sunday after pentecost": "last sunday after pentecost",
    "twenty fourth or last sunday after pentecost": "last sunday after pentecost",
    "octave day of christmas": "octave of the nativity of the lord",
    "holy name of jesus": "most holy name of jesus",
    "votive mass saturday of our lady": "saturday of our lady",
    # feasts of our Lord and our Lady
    "sacred heart of jesus": "most sacred heart of jesus",
    "transfiguration of our lord jesus christ": "transfiguration of our lord",
    "transfiguration of our lord n b on sundays": "transfiguration of our lord",
    "immaculate heart of mary": "immaculate heart of the virgin mary",
    "octave of the assumption the immaculate heart of the virgin mary": "immaculate heart of the virgin mary",
    "queenship of mary": "queenship of the virgin mary",
    "our lady of mount carmel or in carmelite churches solemn commemoration of our lady of mount carmel": (
        "our lady of mount carmel"
    ),
    "our lady of the snows": "dedication of mary of the snows",
    "dedication of the basilica of mary major": "dedication of mary of the snows",
    "dedication of michael the archangel": "dedication of the basilica of michael the archangel",
    "dedication of the basilica of peter paul": "dedication of the basilicas of peter paul",
    "vigil of saints peter paul": "vigil of peter paul",
    "holy seven founders of the order of servants of the virgin mary": "seven holy servite founders",
    # saints
    "teresa of avila": "teresa of jesus",
    "therese of the child jesus the holy face": "therese of the child jesus",
    "theresa of the child jesus": "therese of the child jesus",
    "theresa of the infant jesus": "therese of the child jesus",
    "barnabus": "barnabas",
    "mary magdalen of pazzi": "mary magdalen de pazzi",
    "mary magdalene de pazzi": "mary magdalen de pazzi",
    "anthony mary zaccariah": "anthony mary zaccaria",
    "bernardine of sienna": "bernardine of siena",
    "callistus i": "calistus i",
    "edward the confessor": "edward",
    "gregory thaumaturgus": "gregory the wonderworker",
    "henry the emperor": "henry",
    "jane frances fremiot de chantal": "jane frances de chantal",
    "januarius companions": "januarius",
    "jerome aemiliani": "jerome emiliani",
    "john mary vianney": "jean marie vianney",
    "john the evangelist": "john",  # Dec 27
    "joseph of calasance": "joseph calasance",
    "julia falconieri": "juliana falconieri",
    "julia of falconieri": "juliana falconieri",
    "lawrence justinian": "laurence justinian",
    "luke the evangelist": "luke",
    "margaret mary alacocque": "margaret mary alacoque",
    "pascal baylon": "paschal baylon",
    "philip benize": "philip benizi",
    "stephan of hungary": "stephen of hungary",
    "ubaldus": "ubald",
    "vivian": "bibiana",  # Dec 2, the same martyr
}

_TEMPORAL_SUNDAY = re.compile(r"\bsunday\b|pentecost|easter|dominica", re.I)
_TITLES = re.compile(r"\b(st|saint|ss|blessed|bl)\b\.?")
_LEADING_NUMBER = re.compile(r"^\s*\d+\.?\s+")
_IN_LENT = re.compile(r"^(\w+) sunday in lent$")
_IN_OCTAVE = re.compile(r"^(monday|tuesday|wednesday|thursday|friday|saturday) in the octave of (easter|pentecost)$")


def _fold(s: str) -> str:
    s = s.replace("æ", "ae").replace("Æ", "Ae").replace("œ", "oe").replace("Œ", "Oe")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(name: str) -> str:
    """Stable identity for a celebration: lowercase, no titles, no rank, no punctuation."""
    s = _fold(name).split(",")[0].lower()
    s = re.sub(r"\(.*", "", s)
    s = _LEADING_NUMBER.sub("", s)
    s = _TITLES.sub(" ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    words = s.split()
    if words[:1] == ["the"]:
        words = words[1:]
    if words[-2:] == ["and", "addendum"]:
        words = words[:-2]
    s = " ".join(w for w in words if w != "and")
    s = _IN_LENT.sub(r"\1 sunday of lent", s)
    s = _IN_OCTAVE.sub(r"\2 \1", s)
    return ALIASES.get(s, s)


# Ordinal Sundays, and the last real Sunday of each run (after Pentecost, weeks 24+ are
# resumed Epiphany Sundays and the Last Sunday, so a displaced 23rd is not mapped onward).
_ORDINALS = (
    "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth "
    "fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth"
).split() + [f"twenty {u}" for u in "first second third".split()]
_SEASON_CAP = {"after pentecost": 23, "after easter": 5, "of advent": 4, "of lent": 4, "after epiphany": 6}
_ORDINAL_SUNDAY = re.compile(r"^(?P<ord>[a-z ]+?) sunday (?P<season>" + "|".join(_SEASON_CAP) + r")$")
_NAMED_ORDINAL = {"dominica in albis": ("after easter", 1), "good shepherd sunday": ("after easter", 2)}


def _ordinal(key: str) -> tuple[str, int] | None:
    if key in _NAMED_ORDINAL:
        return _NAMED_ORDINAL[key]
    m = _ORDINAL_SUNDAY.match(key)
    if m and m["ord"] in _ORDINALS:
        return m["season"], _ORDINALS.index(m["ord"]) + 1
    return None


def _sunday_name(ordinal: str, season: str) -> str:
    word, place = season.split()
    return f"{'-'.join(w.capitalize() for w in ordinal.split())} Sunday {word} {place.capitalize()}"


def _shift(anchor: str, anchor_name: str, displaced: int) -> tuple[str, str, int]:
    """The Sunday whose week a feria falls in, `displaced` Sundays after the anchor.

    Returns (key, display name, leftover suffix). When the anchor has an ordinal and the
    target stays within its season, the week is that later Sunday's; otherwise keep +n.
    """
    found = _ordinal(anchor)
    if displaced and found:
        season, n = found
        if n + displaced <= _SEASON_CAP[season]:
            ordinal = _ORDINALS[n + displaced - 1]
            key = f"{ordinal} sunday {season}"
            return ALIASES.get(key, key), _sunday_name(ordinal, season), 0
    return anchor, anchor_name, displaced


_EMBER_SEASON = {2: "lent", 3: "lent", 5: "pentecost", 6: "pentecost", 9: "september", 12: "advent"}
_PENTECOST_EMBER = {"pentecost wednesday", "pentecost friday", "pentecost saturday"}


def _title(name: str) -> str:
    return re.sub(r"\s*\(.*", "", name).strip()


# Offices that genuinely recur on many days of one liturgical year (same Office each time).
RECURRING = {"saturday of our lady"}


def advent_sunday(year: int) -> date:
    """First Sunday of Advent: the Sunday between Nov 27 and Dec 3."""
    d = date(year, 12, 3)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def liturgical_year(d: date) -> int:
    """The liturgical year d belongs to, named by the civil year in which it ends."""
    return d.year + 1 if d >= advent_sunday(d.year) else d.year


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

    def has_earlier(self, d: date) -> bool:
        """True if some earlier date has the same key as d."""
        c = self._entries.get(d)
        return c is not None and self._by_key[c.key][-1] < d

    def unmatched(self, start: date, end: date) -> list[date]:
        """Dates in [start, end] whose key never occurs earlier."""
        return [d for d in sorted(self._entries) if start <= d <= end and not self.has_earlier(d)]

    def span(self) -> tuple[date, date]:
        days = sorted(self._entries)
        return days[0], days[-1]

    def keys(self) -> list[str]:
        return list(self._by_key)

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
    prev: date | None = None
    for d in sorted(rows):
        row = rows[d]
        if prev is not None and d - prev != timedelta(days=1):
            anchor, anchor_name, displaced = None, "", 0  # gap between pages: Sunday unknown
        prev = d
        if row.weekday == "Sunday":
            if _TEMPORAL_SUNDAY.search(row.name):
                anchor, anchor_name, displaced = norm(row.name), _title(row.name), 0
            else:
                displaced += 1
        if row.name.lower().startswith("feria"):
            if anchor is None:
                key, name = f"feria|{d.isoformat()}", "Feria"
            else:
                week_key, week_name, extra = _shift(anchor, anchor_name, displaced)
                tag = week_key if extra == 0 else f"{week_key}+{extra}"
                key = f"feria|{tag}|{row.weekday.lower()}"
                name = f"{row.weekday} after {week_name}"
                if extra:
                    name += f" (+{extra} wk)"
        else:
            key, name = norm(row.name), _title(row.name)
            if "ember" in key.split() or key in _PENTECOST_EMBER:
                # The ordo words ember days inconsistently; the month says which ones they are.
                season = _EMBER_SEASON.get(d.month, f"month-{d.month:02d}")
                key = f"ember|{season}|{row.weekday.lower()}"
            elif key.startswith("greater feria"):
                # Dec 17-23 are fixed to the date: each has its own O antiphon.
                key = f"greater feria of advent|{d:%m-%d}"
        entries[d] = Celebration(key, name)
    return Index(entries)
