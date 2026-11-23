# mosque_discovery

Finds Tunisian mosques from **Mawaqit** and **Google Places**, stores them in a separate
**staging** Postgres/PostGIS DB, dedupes across sources, and lets the main Django app import
approved rows. The service only knows `STAGING_DATABASE_URL`; it never connects to the main DB.

## Flow
1. `discovery` container runs one-shot `crawl` (Mawaqit by default, Google opt-in):
   - Upserts `staged_mosque` on `(source, source_id)` (existing `status` is never overwritten)
   - Cross-source dedupe: Google row within 40 m of a Mawaqit row, or within 150 m with name similarity ≥ 0.6
     → `status='duplicate'`, `duplicate_of_id` set
2. `enrich` step calls self-hosted mawaqit-api to populate `details` JSONB per mosque (run separately or on schedule)
3. A human reviews staging in Django admin and sets `status='approved'` / `'rejected'` with optional notes
4. Main app: `python manage.py import_staged_mosques [--dry-run]` (needs `STAGING_DATABASE_URL`, set for `app` in compose).
   Reads `approved` rows, skips anything within 100 m of an existing Masjid or with a
   ≥0.9 similar name within 1 km (row marked `duplicate`, with `matched_masjid_id`, distance, score), else creates
   Address + Masjid with mawaqit_slug and photo, then marks row `imported`.

## Commands
- `python -m discovery migrate` – run pending SQL migrations
- `python -m discovery crawl [--source mawaqit|google_places] [--max-requests N]` – fetch and upsert (Mawaqit by default)
- `python -m discovery enrich [--limit N] [--delay SECONDS] [--max-age-days DAYS] [--slug SLUG]` – enrich from mawaqit-api

## Run
```
docker compose up -d discovery                      # one-shot crawl
docker compose run --rm discovery python -m discovery crawl --source mawaqit
docker compose run --rm discovery python -m discovery crawl --source google_places --max-requests 300
docker compose run --rm discovery python -m discovery enrich --limit 100
docker compose run --rm discovery python -m discovery migrate
docker compose exec app python manage.py import_staged_mosques --dry-run
```
`STAGING_DATABASE_URL` is required in both discovery and app containers. `GOOGLE_PLACES_API_KEY` and
`MAWAQIT_API_TOKEN` come from the shell/.env of the compose host; never commit them.
Without the key, Google is skipped with a warning.

## Sources
* **mawaqit** – map endpoint `GET https://mawaqit.net/api/2.0/mosque/map/TN` (unauthenticated, ~2.5k mosques).
  Enrichment via self-hosted `mrsofiane/mawaqit-api` (requires `MAWAQIT_API_TOKEN`).
* **google_places** – Places API (New) Text Search (opt-in, billable).

## Tests
```
pip install -r requirements-dev.txt
pytest mosque_discovery/tests
```
Adapters (with mocked HTTP), dedupe, migrations. DB tests run if `STAGING_TEST_DATABASE_URL` is set.
Import-command tests: `nasjod/core/tests/test_import_staged_mosques.py` (run with app's pytest setup).
