# ViewTrack

Search Downloadha / DLFox for a game, add pages to a watchlist, and let a
background scheduler keep taking view-count snapshots automatically.

## Run it

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## How it's structured

- `scraper.py` — one generic scraper driven by a config per site (`SITES` dict),
  instead of duplicating the same logic twice. Uses a `requests.Session` with
  retry/backoff, and a small delay between page fetches.
- `database.py` — SQLite (`tracker.db`, created automatically). Two tables:
  `tracked_games` (your watchlist) and `view_snapshots` (one row per scrape,
  per game, over time).
- `scheduler.py` — APScheduler background job that walks the whole watchlist
  and takes a fresh snapshot for each game. Runs every `AUTO_REFRESH_HOURS`
  hours (default 6) — set the env var to change it, e.g.:
  ```bash
  AUTO_REFRESH_HOURS=2 python app.py
  ```
- `app.py` — Flask routes. `/api/search` now fetches Downloadha and DLFox in
  parallel with a thread pool instead of sequentially.
- `templates/dashboard.html` — search box + results, and a watchlist section
  where each row shows the latest view count, the change since the previous
  snapshot, and (click the row) a history chart.

## Notes / next steps worth considering

- The scheduler is in-process: if you restart the app, the "every N hours"
  clock resets. For a production deployment, a real cron job or Celery beat
  calling `/api/refresh-all` would survive restarts.
- No de-duplication of games across sites yet — the same title tracked on
  both Downloadha and DLFox shows as two separate rows, which is probably
  what you want but worth confirming.
- Scraping is inherently fragile against site redesigns (CSS selectors will
  break silently and just show "N/A"). Worth adding a simple alert/log when
  a scrape returns `None` for several runs in a row, so you notice before
  your history has a silent gap.
- No auth — if you deploy this somewhere reachable from the internet, add at
  least basic auth in front of it.
