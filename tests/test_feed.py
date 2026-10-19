import xml.etree.ElementTree as ET
from datetime import date
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from barroux_daily.episodes import Episode
from barroux_daily.feed import pub_date, render_feed

NS = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}
NY = "America/New_York"


def ep(day, hour, recorded=None, url=None, celebration="St. Teresa of Jesus, Virgin & Doctor",
       same_feast=True, source_celebration=None):
    recorded = recorded or date(2025, day.month, day.day)
    url = url or f"https://cdn.barrouxchant.com/{recorded.isoformat()}-{hour}.mp3"
    return Episode(day, hour, recorded, url, celebration, same_feast, source_celebration)


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
    assert "recorded Wednesday, October 15, 2025" in description
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
    ch = parse([(ep(d, "lauds", celebration=None, same_feast=None), 5)])
    item = ch.find("item")
    assert item.findtext("title") == "Thu Mar 4 · Lauds"
    assert item.findtext("description").startswith(
        "? Unchecked: matched by calendar date only (liturgical calendar not yet available)"
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


MON = date(2026, 10, 19)


def describe(e):
    return parse([(e, 1)]).find("item").findtext("description")


def test_same_feast_same_weekday_is_marked_right():
    text = describe(ep(MON, "terce", recorded=date(2020, 10, 19)))
    assert text.startswith("✓ Right: same feast, same weekday.")
    assert "Terce, recorded Monday, October 19, 2020." in text
    assert "Breviarium Meum" not in text


def test_weekday_hour_from_another_feast_has_right_psalms_but_points_to_breviarium_meum():
    text = describe(ep(MON, "sext", recorded=date(2022, 10, 24), same_feast=False,
                       source_celebration="Monday after Twenty-First Sunday after Pentecost"))
    assert text.startswith("◐ Psalms right")
    assert "Monday after Twenty-First Sunday after Pentecost" in text
    assert "Breviarium Meum" in text


def test_weekday_hour_from_another_weekday_is_marked_wrong():
    text = describe(ep(MON, "none", recorded=date(2024, 10, 19)))
    assert text.startswith("✗ Psalms differ: recorded on a Saturday.")
    assert "Breviarium Meum" in text


def test_lauds_of_the_same_feast_on_another_weekday_may_differ():
    text = describe(ep(MON, "lauds", recorded=date(2024, 10, 19)))
    assert text.startswith("◐ Same feast, recorded on a Saturday.")
    assert "Breviarium Meum" in text


def test_lauds_from_another_celebration_is_marked_wrong():
    text = describe(ep(MON, "vespers", recorded=date(2020, 10, 19), same_feast=False, source_celebration="St. X"))
    assert text.startswith("✗ Different feast: St. X.")
