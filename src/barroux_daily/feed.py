from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, time, timedelta
from email.utils import format_datetime
from zoneinfo import ZoneInfo

from .episodes import HOUR_LABELS, HOURS, Episode

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


def _description(ep: Episode) -> str:
    text = (
        f"{HOUR_LABELS[ep.hour]}, recorded {ep.recorded:%B} {ep.recorded.day}, {ep.recorded.year}. "
        "Chanted by the monks of Sainte-Madeleine du Barroux."
    )
    if ep.celebration is None:
        text += (
            " This day was matched by calendar date (liturgical calendar not yet available), "
            "so movable feasts may differ."
        )
    return text


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
