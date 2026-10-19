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
    assert ch.find("itunes:image", NS).get("href") == "https://example.github.io/barroux-daily/cover.jpg"


def test_item_fields_for_a_liturgically_matched_episode():
    d = date(2026, 10, 15)
    ch = parse([(ep(d, "none"), 46082089)])
    (item,) = ch.findall("item")
    assert item.findtext("title") == "Thu Oct 15 · Nones · St. Teresa of Jesus, Virgin & Doctor"
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
    assert item.findtext("title") == "Thu Mar 4 · Lauds"
    assert item.findtext("description").endswith(
        " This day was matched by calendar date (liturgical calendar not yet available), "
        "so movable feasts may differ."
    )


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


def test_lead_days_dates_episodes_early_so_upcoming_days_are_not_future_dated():
    zone = ZoneInfo(NY)
    d = date(2025, 10, 17)
    assert pub_date(ep(d, "lauds"), zone, lead_days=2).isoformat() == "2025-10-15T00:01:00-04:00"
