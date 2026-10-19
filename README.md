# barroux-daily

An unlisted podcast feed (public repo; kept out of podcast directories) of today's
Divine Office, chanted by the monks of Le Barroux, for praying with. barrouxchant.com records the monks' stream but posts irregularly.
This takes today's liturgical day (from the propria.org ordo), finds the same
celebration in earlier years, and fills each hour from the newest recording that
has it. It rebuilds every day.

The feed holds just today and tomorrow, so a late or skipped build never
leaves today empty. Titles start with the day they are
for (`Mon Oct 19 · Lauds · St. Peter of Alcantara, Confessor`). Episodes are dated
one day early so podcast apps don't hide the upcoming ones.

Audio is never copied: episodes stream from `cdn.barrouxchant.com`.

## Subscribe

Feed URL: `https://<github-user>.github.io/barroux-daily/feed.xml`

- Apple Podcasts: Library > ... > Follow a Show by URL
- Overcast / Pocket Casts / Castro / AntennaPod: add by URL
- Spotify: not supported. Spotify only takes public submissions, and these recordings
  belong to the abbey. Do not submit this feed publicly without their permission.

## How it matches

Saints and named days match by name (`St. Teresa of Jesus`, `Twenty-First Sunday after
Pentecost`). Ferias match as "weekday after Sunday X", so a Wednesday in Oct 2026 can be
filled from a Wednesday in November 2019; when a feast takes a Sunday's place (Christ the
King on the 22nd Sunday after Pentecost, say), that week's ferias still match as the 22nd week. Ember days match by season, and the Greater Ferias of Advent (Dec 17-23,
each with its own O antiphon) by calendar date. Each episode says when it was recorded.

The ordo is the Roman 1962 Mass calendar; Le Barroux is Benedictine, so on a few days
their Office may differ from the match. If a day looks off, add an alias in
`src/barroux_daily/liturgy.py` (`ALIASES`) and run `python -m barroux_daily.ordo_index`,
which lists keys seen on only one date, near-duplicate keys, and the days of the newest
full liturgical year with no earlier match.

## Run locally

```bash
pip install -e '.[dev]'
pytest
python -m barroux_daily.ordo_index   # refresh data/ordo_index.json (~35 s)
python -m barroux_daily.build        # writes public/feed.xml
```

Config (environment variables):

| Variable | Default | |
| --- | --- | --- |
| `FEED_TZ` | `America/New_York` | whose "today" the feed follows |
| `FEED_BASE_URL` | `http://localhost:8000` | where the feed is served |
| `OUT_DIR` | `public` | where `feed.xml` and `index.html` are written |
| `ORDO_INDEX` | `data/ordo_index.json` | the liturgical index |

In GitHub Actions, `FEED_TZ`, `FEED_BASE_URL` and the build times (cron) are set in
`.github/workflows/daily.yml`. It builds twice a day (06:17 and 13:17 UTC; the second run
picks up recordings posted that day). `.github/workflows/refresh-ordo.yml` refreshes the
ordo index weekly.

## Keeping it running

GitHub disables scheduled workflows in a public repo after 60 days with no repository
activity. That turns off both `daily-feed` (the feed stops updating) and `refresh-ordo` (next
year's ordo stops arriving too). GitHub emails the owner before it does this. To turn them back
on, open the repo's Actions tab, select each workflow, and click "Enable workflow".
