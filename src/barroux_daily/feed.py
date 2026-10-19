from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, time, timedelta
from email.utils import format_datetime
from zoneinfo import ZoneInfo

from .episodes import HOUR_LABELS, HOURS, WEEKDAY_HOURS, Episode

ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ET.register_namespace("itunes", ITUNES)

COVER = "cover.jpg"  # copied next to feed.xml by build.main
AUTHOR = "Abbaye Sainte-Madeleine du Barroux"


def _q(tag: str) -> str:
    return f"{{{ITUNES}}}{tag}"


def _text(parent: ET.Element, tag: str, value: str, **attrs: str) -> ET.Element:
    el = ET.SubElement(parent, tag, attrs)
    el.text = value
    return el


def pub_date(ep: Episode, zone: ZoneInfo, lead_days: int = 0) -> datetime:
    """Local midnight + (hour index + 1) minutes, so hours sort in liturgical order.

    lead_days shifts every episode earlier so upcoming days are never future-dated
    (podcast apps hide episodes published in the future).
    """
    day = ep.day - timedelta(days=lead_days)
    return datetime.combine(day, time(0, HOURS.index(ep.hour) + 1), tzinfo=zone)


def _title(ep: Episode) -> str:
    when = f"{ep.day:%a %b} {ep.day.day}"
    label = HOUR_LABELS[ep.hour]
    return f"{when} · {label} · {ep.celebration}" if ep.celebration else f"{when} · {label}"


CHECK = "For today's antiphon, chapter and prayer, see Breviarium Meum."


def _verdict(ep: Episode) -> str:
    """How far this recording matches the day under the 1963 monastic rubrics."""
    weekday = f"{ep.recorded:%A}"
    same_weekday = ep.recorded.weekday() == ep.day.weekday()
    if ep.same_feast is None:
        return (
            "? Unchecked: matched by calendar date only (liturgical calendar not yet available), "
            f"so movable feasts may differ. {CHECK}"
        )
    if ep.hour in WEEKDAY_HOURS:  # psalms always from the weekday
        if not same_weekday:
            return f"✗ Psalms differ: recorded on a {weekday}. {CHECK}"
        if ep.same_feast:
            return "✓ Right: same feast, same weekday."
        return f"◐ Psalms right, but recorded on {ep.source_celebration}. {CHECK}"
    if not ep.same_feast:
        return f"✗ Different feast: {ep.source_celebration}. {CHECK}"
    if same_weekday:
        return "✓ Right: same feast, same weekday."
    return (
        f"◐ Same feast, recorded on a {weekday}. Greater feasts have their own psalms; "
        f"on lesser feasts the psalms follow the weekday and may differ. {CHECK}"
    )


def _description(ep: Episode) -> str:
    return (
        f"{_verdict(ep)} {HOUR_LABELS[ep.hour]}, recorded {ep.recorded:%A, %B} {ep.recorded.day}, "
        f"{ep.recorded.year}.{_new_calendar(ep)} Chanted by the monks of Sainte-Madeleine du Barroux."
    )


def _new_calendar(ep: Episode) -> str:
    return f" New calendar: {ep.new_calendar}." if ep.new_calendar else ""


def render_feed(items: list[tuple[Episode, int]], tz: str, base_url: str, lead_days: int = 0) -> bytes:
    zone = ZoneInfo(tz)
    rss = ET.Element("rss", {"version": "2.0"})
    ch = ET.SubElement(rss, "channel")
    _text(ch, "title", "Barroux Chant: Today's Office")
    _text(ch, "link", base_url)
    _text(
        ch,
        "description",
        "The Divine Office chanted by the monks of Le Barroux, for today's liturgical day, "
        "assembled from the barrouxchant.com archive. Unlisted feed.",
    )
    _text(ch, "language", "la")
    _text(ch, _q("author"), AUTHOR)
    _text(ch, _q("explicit"), "no")
    _text(ch, _q("type"), "episodic")
    _text(ch, _q("block"), "yes")
    ET.SubElement(ch, _q("image"), {"href": f"{base_url}/{COVER}"})
    cat = ET.SubElement(ch, _q("category"), {"text": "Religion & Spirituality"})
    ET.SubElement(cat, _q("category"), {"text": "Christianity"})

    for ep, length in sorted(items, key=lambda it: pub_date(it[0], zone, lead_days), reverse=True):
        item = ET.SubElement(ch, "item")
        _text(item, "title", _title(ep))
        _text(item, "description", _description(ep))
        _text(item, "guid", f"barroux-daily:{ep.day.isoformat()}:{ep.hour}", isPermaLink="false")
        _text(item, "pubDate", format_datetime(pub_date(ep, zone, lead_days)))
        ET.SubElement(
            item,
            "enclosure",
            {"url": ep.url, "length": str(length), "type": "audio/mpeg"},
        )
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)
