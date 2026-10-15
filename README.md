# barroux-daily

A private podcast feed of today's Divine Office, chanted by the monks of Le Barroux,
for praying with. barrouxchant.com records the monks' stream but posts irregularly.
This takes today's liturgical day (from the propria.org ordo), finds the same
celebration in earlier years, and fills each hour from the newest recording that
has it. It rebuilds every day.

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
filled from a Wednesday in November 2019. Each episode says when it was recorded.

The ordo is the Roman 1962 Mass calendar; Le Barroux is Benedictine, so on a few days
their Office may differ from the match. If a day looks off, add an alias in
`src/barroux_daily/liturgy.py` (`ALIASES`) and run `python -m barroux_daily.ordo_index`.

## Run locally

```bash
pip install -e '.[dev]'
pytest
python -m barroux_daily.ordo_index   # refresh data/ordo_index.json (~35 s)
python -m barroux_daily.build        # writes public/feed.xml
```

Config: `FEED_TZ` (default `America/New_York`), `FEED_BASE_URL`, `OUT_DIR`, `ORDO_INDEX`.
