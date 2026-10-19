# Barroux Daily: design

## Problem

barrouxchant.com auto-records the Divine Office the monks of Le Barroux stream each day, but the recordings are posted inconsistently (some days have only one or two hours; today has none). I want to open a podcast app and find the chant for *today's liturgical day*, every day, reliably, to pray with. This is a personal prayer tool, not a product.

## Sources (verified 2026-10-15)

**barrouxchant.com** (the audio)
- `GET https://barrouxchant.com/api/hours/YYYY-MM-DD.json` returns `{hour: mp3_url}`; an empty day returns `{}` (HTTP 200). Keys: `lauds prime terce sext none vespers compline unknown` (`unknown` is unclassified).
- mp3s live at `https://cdn.barrouxchant.com/YYYY-MM-DD-<hour>.mp3`; 20-46 MB, `audio/mpeg`, `Content-Length` present.
- Sampled coverage: 2013-2016 none, 2017 partial, 2018-2025 complete, 2026 partial. Individual days often lack hours. No Matins.
- The site's own feedburner podcast feed is stale.

**propria.org ordo** (the liturgical calendar: which celebration falls on which date)
- Monthly pages `https://propria.org/calendar/liturgical-calendar-YYYY-MM/` for 2017-01 through 2018-11; annual pages `https://propria.org/archived-YYYY/` for 2019-2025 (each runs from the first Sunday of Advent, e.g. 2018-12-01 to 2019-12-01); `https://propria.org/ordo-2026/` for the current year (2025-11-30 to 2026-11-30). Next year's page appears as `ordo-2027`.
- Each page is an HTML table: date, weekday, Mass name, class, colour. Alternate celebrations (e.g. "in Carmelite churches") are extra rows with a blank date.
- Sundays carry stable names ("Twenty-First Sunday after Pentecost"). Ferias are just "Feria", with no week, so they need the preceding Sunday as an anchor. Saint names drift between years ("St. Teresa of Avila" in 2018, "St. Teresa of Jesus" in 2026).
- This is the Roman 1962 ordo for Mass. Le Barroux is Benedictine, and their Office follows the monastic calendar, which differs on some days. The ordo is a good proxy, not a perfect one.

**neumz.com** is not used. It is a patron-gated product ("Become a Neumz patron to unlock all chants"); its audio is per-chant, signed-URL, and behind accounts. It is a good picture of what a full liturgical-day player looks like, and that is far more than this project needs.

## Design

A static RSS feed, rebuilt daily by GitHub Actions and served from GitHub Pages.

1. **Ordo index (committed data, refreshed monthly).** `python -m barroux_daily.ordo_index` fetches every ordo page 2017 to now, parses the tables, and writes `data/ordo_index.json`: `date -> (key, display name)`.
   - Sundays and named days: key = normalized name (`twenty first sunday after pentecost`, `teresa of jesus`; known spelling variants aliased).
   - Ferias: key = `feria|<preceding temporal Sunday>|<weekday>`, so "Wednesday after the 21st Sunday after Pentecost" matches across years even when it lands in November. If a Sunday is displaced by a feast, the following ferias get a `+n` suffix so keys stay unique within a year.
2. **Daily build.** For today's date, look up its key. The candidate dates are every earlier date (2017 on) with the same key, newest first. For each of the 7 hours, take the first candidate that has a recording. This gives one full set per day, mostly from the most recent year where that celebration fell.
3. If today is not in the index (e.g. the new ordo year isn't published yet), fall back to same month/day and say so in the episode description.
4. One episode per hour; titles read "Thu Oct 15 · Lauds · St. Teresa of Jesus, Virgin & Doctor". Enclosures point straight at `cdn.barrouxchant.com`. The feed carries the last 7 days plus the next 2 days. Episode `pubDate`s are 00:01 to 00:07 local time in hour order, shifted 2 days earlier than the day they are for, so upcoming days are never future-dated.
5. Private feed (`itunes:block yes`), added to a podcast app by URL.

## Decisions and non-goals

- Private feed, not a public Spotify listing: Spotify has no add-by-URL and the recordings belong to the abbey. Apple Podcasts "Follow a Show by URL", Overcast, Pocket Casts, Castro, AntennaPod all work.
- No Matins, no Mass propers, no neumes, no notation, no per-chant audio. Just the day's hours.
- No audio mirroring, no database, no web UI beyond a one-line index page.
- Timezone is configurable (`FEED_TZ`, default `America/New_York`).
- Where the monastic and Roman calendars differ, the match may be a plausible neighbour rather than the exact day. Eyeball the first few weeks and add aliases in `liturgy.ALIASES` as needed.
