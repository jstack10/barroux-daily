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
        text += " Also matched by calendar date (liturgical calendar unavailable), so movable feasts may differ."
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
