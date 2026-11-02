# mosque_discovery

Finds Tunisian mosques from **Mawaqit** and **Google Places**, stores them in a separate
**staging** Postgres/PostGIS DB, dedupes across sources, and lets the main Django app import
approved rows. The service only knows `STAGING_DATABASE_URL`; it never connects to the main DB.

## Flow
1. `discovery` container crawls every `CRAWL_INTERVAL_HOURS` (default 168 = weekly) → upserts `staged_mosque`
   on `(source, source_id)` (existing `status` is never overwritten) → cross-source dedupe
   (Google row within 40 m of a Mawaqit row, or within 150 m with name similarity ≥ 0.6 → `status='duplicate'`, `duplicate_of_id` set).
2. A human reviews staging and sets `status='approved'` / `'rejected'` (plain SQL or any DB client):
   `UPDATE staged_mosque SET status='approved' WHERE id IN (...);`
3. Main app: `python manage.py import_staged_mosques [--dry-run] [--auto]` (needs `STAGING_DATABASE_URL`, set for `app` in compose).
   Reads `approved` rows (`--auto` adds `new`), skips anything within 100 m of an existing Masjid or with a
   ≥0.9 similar name within 1 km (row marked `duplicate`, with `matched_masjid_id`, distance, score), else creates
   Address + Masjid like `import_mosques_from_csv` and marks the row `imported`.

## Run
```
docker compose up -d staging_db discovery                      # periodic loop
docker compose run --rm discovery python -m discovery crawl     # one-shot, all sources
docker compose run --rm discovery python -m discovery crawl --source mawaqit
GOOGLE_PLACES_API_KEY=... docker compose run --rm discovery python -m discovery crawl --source google_places --max-requests 300
docker compose exec app python manage.py import_staged_mosques --dry-run
```
`GOOGLE_PLACES_API_KEY` and `STAGING_DB_PASSWORD` come from the shell/.env of the compose host; never commit them.
Without the key, Google is skipped with a warning.

## Sources
* **mawaqit** – no official public API. `/api/2.0/mosque/search` needs a token (401), but the site's map endpoint
  `GET https://mawaqit.net/api/2.0/mosque/map/TN` is unauthenticated and returns all ~2.5k Tunisian mosques in one
  request (name, address, city, zip, lat/lng, image). One request per crawl, identifying User-Agent, retry/backoff.
  **ToS risk**: undocumented endpoint, no explicit licence for bulk reuse; get Mawaqit's written OK before production
  use (`MAWAQIT_API_TOKEN` is honoured if they give us one). No prayer times are taken.
* **google_places** – Places API (New) Text Search, `includedType=mosque`, quadtree over Tunisia's bbox (cells that hit
  the 60-result cap are split until 0.02°), filtered to country TN. Billable: use `--max-requests`. Google's terms restrict
  storing Places content beyond the place ID long-term and require showing it on a Google map; confirm the licensing
  fits before importing Google-sourced names/phones into the main DB.

## Tests
`pip install -r requirements.txt && pytest` (adapters with mocked HTTP, dedupe). DB test runs if
`STAGING_TEST_DATABASE_URL` points at a PostGIS DB. Import-command tests: `nasjod/core/tests/test_import_staged_mosques.py`
(run with the main app's pytest setup).
