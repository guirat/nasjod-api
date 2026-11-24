# GUI-22 Backend plan: mosque discovery as a separate service, staging DB, human review

Owner: Backend Tech Lead. Implementer: Backend Developer.
Branch: `feature/GUI-22-mosque-discovery` (from `origin/staging`). PR target: `staging`.

## Decisions already taken (board, on GUI-22)

| Topic | Decision |
|---|---|
| Shape | Separate image + separate container, same repo (`mosque_discovery/`). |
| Database | Separate **database + role** (`staging`) on the **existing** Postgres server. No `staging_db` container. |
| Sources | Mawaqit only for now. Google stays in the code but is opt-in only. |
| Frequency | On demand; can be scheduled (Coolify scheduled task). One-shot runs, no in-container loop. |
| Review | Manual review only. Nothing reaches `Masjid` without a human approval. |
| Mawaqit data | List of TN mosques (map endpoint or the archived `TN` JSON the board exported from web.archive.org), details per mosque via a **self-hosted** `mrsofiane/mawaqit-api`. |
| Mawaqit permission | Board decided not to ask Mawaqit. Residual risk recorded below; mitigations are mandatory. |
| Prayer times | **Out of scope.** Board wants meteo.tn as the prayer-time source: separate issue. We only keep the Mawaqit slug on `Masjid` so it can be linked later. |

## Technical approach

The code on `main` (commit `2c3e360`) already has the right skeleton: a Django-free worker that writes
`staged_mosque` in its own DB, and a Django command that imports approved rows into `Masjid`. We keep it
and fix what blocks production:

1. Staging lives in its own DB/role on the main Postgres server, so it is backed up with everything else.
2. The worker becomes one-shot (`crawl`, `enrich`), Mawaqit by default.
3. The Mawaqit list can come from the live map endpoint **or** a JSON file/URL (archived export).
4. A new `enrich` step fills per-mosque details from our own mawaqit-api instance (internal network only).
5. Review moves from raw SQL to Django admin (approve/reject with who/when).
6. Import keeps the Mawaqit slug, the photo and the service flags, and loses `--auto`.
7. Versioned SQL migrations for the staging schema; image built and pushed by CI.

Why mawaqit-api is **enrichment, not discovery**: every endpoint takes one known slug, there is no
list/search. The slug list comes from the map/`TN` JSON; mawaqit-api gives the details for each slug.

## Branch base (important)

`main` and `staging` diverged: `main` has only `2c3e360` (discovery) on top; `staging` has 33 commits
(GUI-2/8/16/18: new CI, Coolify deploy) that `main` lacks. Base the work on `origin/staging` and
**cherry-pick `2c3e360`** as the first commit. Do not merge `main` (its old `ci-cd.yml` conflicts).

## Contract

### Public REST API

**No change.** No new endpoint, no serializer change. `Masjid.mawaqit_slug` is **not** exposed in the
API in this issue. Frontend Tech Lead: no impact.

### Shared contract: `staged_mosque` (staging DB)

The worker owns the schema (SQL migrations in `mosque_discovery/migrations/`). Django reads it through an
**unmanaged** model and never migrates it. Column ownership:

| Column | Type | Written by |
|---|---|---|
| `id`, `source`, `source_id` (unique together), `name`, `name_ar`, `lat`, `lon`, `geom`, `address`, `city`, `state`, `zip_code`, `country`, `phone`, `raw`, `first_seen`, `last_seen` | existing | worker `crawl` |
| `image_url` TEXT NULL (new) | normalised https URL, no web.archive.org wrapper | worker `crawl` |
| `details` JSONB NULL (new) | mawaqit-api raw-data response | worker `enrich` |
| `enriched_at` TIMESTAMPTZ NULL, `enrich_error` TEXT NULL (new) | | worker `enrich` |
| `status` (existing CHECK: `new`/`approved`/`rejected`/`imported`/`duplicate`) | | worker sets only `new` (insert) and `duplicate` (dedupe of `new` rows); Django sets the rest |
| `reviewed_by_id` BIGINT NULL, `reviewed_by_username` TEXT NULL, `reviewed_at` TIMESTAMPTZ NULL, `review_note` TEXT NULL (new) | | Django admin |
| `duplicate_of_id`, `matched_masjid_id`, `match_distance_m`, `match_name_score` | existing | worker dedupe / Django import |

Rules: the worker upsert never overwrites `status`, `reviewed_*`, `matched_*` (already true, keep it).
`reviewed_by_id` is a plain id (no cross-DB FK); `reviewed_by_username` keeps the audit readable.

Status transitions (enforced in Django, tested):
`new → approved | rejected`, `duplicate → approved | rejected` (human override),
`approved → imported | duplicate` (import), `rejected → new` (undo). `imported` is final.

### Worker CLI (`python -m discovery ...`)

| Command | Behaviour | Exit code |
|---|---|---|
| `migrate` (replaces `init-db`) | applies pending `migrations/NNNN_*.sql` in order, each in a transaction, recorded in `schema_migrations` | 0 ok, 1 error |
| `crawl [--source mawaqit] [--mawaqit-input URL_OR_PATH] [--country TN]` | one run, then exits. Default source: `mawaqit` only. `google_places` runs only if passed explicitly **and** the key is set. | 0 ok, 1 if any source failed |
| `enrich [--limit N] [--delay SECONDS] [--max-age-days 30] [--slug SLUG]` | calls mawaqit-api for `source='mawaqit'` rows with status `new`/`approved` whose `enriched_at` is null or older than max-age | 0 ok (per-row errors recorded in `enrich_error`), 1 if mawaqit-api unreachable |

`loop` is removed. `crawl` and `enrich` run `migrate` first (idempotent).

### Environment

| Var | Container | Required |
|---|---|---|
| `STAGING_DATABASE_URL` | discovery, app | yes in discovery (fail fast, no default password); optional in app (staging admin hidden if unset) |
| `MAWAQIT_API_URL` (e.g. `http://mawaqit_api:8000`) | discovery | for `enrich` |
| `MAWAQIT_API_TOKEN` | discovery, mawaqit_api | yes when `enrich` runs |
| `MAWAQIT_INPUT` | discovery | optional, default live map URL |
| `GOOGLE_PLACES_API_KEY` | discovery | optional |

The discovery container never receives main-DB credentials. The app container never receives the
mawaqit-api token or Google key.

## Data model changes

### Staging DB (SQL, reversible)
- `migrations/0001_initial.sql`: today's `schema.sql` as-is (so existing staging DBs are detected:
  if `staged_mosque` exists and `schema_migrations` doesn't, record 0001 as applied without running it).
- `migrations/0002_review_and_enrichment.sql` + `0002_review_and_enrichment.down.sql`: the new columns
  above, plus index on `(source, enriched_at)`.
- Delete `schema.sql`.

### Main DB (Django migration, reversible)
- `Masjid.mawaqit_slug = CharField(max_length=255, null=True, blank=True, unique=True)`.
  Nullable + unique is safe on Postgres (multiple NULLs allowed). Auto-generated `AddField` is reversible.

## Task breakdown (ordered, one commit each, small PR)

### T0. Branch setup
Branch from `origin/staging`, cherry-pick `2c3e360`.
- AC: `git log` shows the cherry-pick on top of staging; existing tests in `mosque_discovery/tests` and
  `core/tests/test_import_staged_mosques.py` pass.

### T1. Staging schema migrations
Add `migrations/` runner in `store.py` (`schema_migrations(version TEXT PK, applied_at)`), files 0001/0002
(+down for 0002), `migrate` command, adopt-existing logic.
- AC: on an empty DB, `migrate` creates everything; second run is a no-op; on a DB created by the old
  `schema.sql`, `migrate` records 0001 and applies only 0002; applying `0002...down.sql` returns to 0001 shape.

### T2. One-shot worker, Mawaqit by default
Remove `loop`. `crawl` default sources = `['mawaqit']`. Exit 1 if any source fails. Dockerfile:
`CMD ["python", "-m", "discovery", "crawl"]`, stop copying `tests/`, keep pytest out of the runtime
image (`requirements-dev.txt`). Update README.
- AC: `crawl` with no `--source` never instantiates the Google adapter even if the key is set;
  `--source google_places` without key logs a warning and exits 0 for that source; failing source → exit 1.

### T3. Mawaqit input from file/URL + image URL
`MawaqitAdapter(input=...)`: if input is an `http(s)` URL, GET it (same retry/backoff); else read a
local JSON file. Same parser for both (same format as the board's `TN` export). Normalise `image1`:
strip a `https://web.archive.org/web/<digits>[a-z_]*/` prefix, unescape `\/`, keep only `https://`
URLs, store in `image_url`. Default input stays the live map URL.
- AC: tests with a fixture containing the two sample rows from GUI-22 (archived format) produce the
  right slugs, names, coords and `image_url = https://cdn.mawaqit.net/...`; a non-https or malformed
  `image1` gives `image_url = NULL`; the live-URL path still works with a mocked session.

### T4. Enrichment via self-hosted mawaqit-api
- `discovery/enrich.py`: for each selected row, `GET {MAWAQIT_API_URL}/api/v1/{slug}/` (raw-data
  endpoint; confirm exact path against the pinned version) with `Authorization: Bearer <token>`,
  timeout 30 s, `--delay` between calls (default 2 s), retry/backoff on 429/5xx. Store JSON in
  `details`, set `enriched_at`, clear `enrich_error`. 404 → `enrich_error='not_found'`. Other errors
  → `enrich_error=<short message>`, row skipped, run continues. Commit every row (or small batch).
- Compose service `mawaqit_api`: built from a **pinned commit** of `mrsofiane/mawaqit-api`
  (`build.context: https://github.com/mrsofiane/mawaqit-api.git#<SHA>`) + `redis` service for its cache.
  Auth enabled with `MAWAQIT_API_TOKEN` (use the upstream env var names, verify in its README at that SHA).
  **No `ports:`** (internal network only).
- AC: unit tests with a mocked HTTP session cover success, 404, 5xx-then-success, timeout, and the
  selection query (skips `rejected`/`imported`/`duplicate`, skips fresh `enriched_at`, respects `--limit`).
  Token never appears in logs.

### T5. Staging DB on the existing Postgres
- Remove `staging_db` service and `staging_data` volume from both compose files. `discovery` gets
  `STAGING_DATABASE_URL` without a default (`${STAGING_DATABASE_URL:?STAGING_DATABASE_URL is required}`),
  `restart: "no"`.
- `docs/ops/GUI-22.md`: one-time SQL to run as superuser (`CREATE ROLE staging LOGIN PASSWORD ...;
  CREATE DATABASE staging OWNER staging; \c staging; CREATE EXTENSION postgis;`), `REVOKE CONNECT ON
  DATABASE <main> FROM PUBLIC` check so `staging` cannot connect to the main DB, the Coolify scheduled
  tasks (`crawl` then `enrich`), and confirm `backup_db_to_r2` covers the `staging` database (if it dumps
  only `DB_NAME`, say so and add it in the ops doc as a required follow-up).
- AC: `docker compose config` passes with the var set and fails clearly without it; the role
  `staging` cannot `\c` the main DB (documented check).

### T6. Django: staging DB + admin review
- `settings.py`: if `STAGING_DATABASE_URL` is set, add `DATABASES['staging']` (postgis engine, parsed
  from the URL, `CONN_MAX_AGE=0`). `core/db_routers.py`: models with `app_label='discovery_staging'` (or a
  `staging_db = True` marker) read/write `staging`; `allow_migrate` returns False for them on every DB.
- New app `staging_review` with unmanaged `StagedMosque` (`managed = False`, `db_table='staged_mosque'`).
- Admin: list (name, name_ar, city, status, enriched?, first_seen, matched_masjid_id), filters by
  status/source/enriched, search by name/city/slug, read-only fields, link to `https://mawaqit.net/fr/<slug>`
  and to OSM at lat/lon. Actions: **Approve**, **Reject** (sets `reviewed_*`, enforces the transition
  table), **Import approved** (calls the import service from T7 for the selected approved rows).
  Delete permission disabled. Only superusers or a `staging_review.review_stagedmosque` permission.
- Not registered when `staging` DB is not configured.
- AC: tests (with a test `staging` DB, or `databases = {'default', 'staging'}` and the table created in a
  fixture) cover approve/reject, forbidden transitions, `reviewed_by_*` set, non-staff gets 403/302,
  admin hidden without the setting; `manage.py migrate` never touches the staging DB.

### T7. Import: no `--auto`, slug, details, photo
- Move the import logic into `core/services/staged_import.py` used by both the command and the admin action.
- Remove `--auto`. Only `approved` rows are imported.
- Add `Masjid.mawaqit_slug` (migration). Set it from `source_id` when `source='mawaqit'`.
  Dedupe: an existing `Masjid` with the same `mawaqit_slug` counts as a match before distance/name checks.
- Map `details` → `Masjid` booleans when present (parking, disabled_access, ablution_room, woman_space,
  adult_courses, children_courses, salat_al_eid, salat_al_janaza); phone from details if row phone empty.
  Build the key map from a **recorded real response** of the pinned mawaqit-api (commit it as a test
  fixture); unknown/missing keys → leave the default.
- Photo: download `image_url` only if host is `cdn.mawaqit.net`, `https`, `Content-Type: image/*`,
  ≤ 5 MB, timeout 20 s; save to `Masjid.photo` via the default storage. Any failure → mosque still
  imported without photo, warning printed.
- Transaction: `Address` + `Masjid` + photo in one `transaction.atomic()` on `default`; staging row
  marked `imported` only after commit. If marking fails, the next run finds the mosque by slug and marks
  it `duplicate` with `matched_masjid_id` (no double insert).
- AC: tests cover: approved imported with slug/flags; `new` rows ignored; existing slug → duplicate;
  photo host not allowed → no download; photo 404/oversize → imported without photo; dry run changes nothing;
  migration forward/backward.

### T8. CI/CD
- `ci.yml`: add job `discovery-test` (python 3.12, `pip install -r mosque_discovery/requirements.txt
  -r mosque_discovery/requirements-dev.txt`, `pytest mosque_discovery/tests`; tests needing Postgres use a
  `postgis/postgis` service like the existing `test` job).
- `deploy.yml`: build and push `ghcr.io/<owner>/nasjod-discovery` with the same env/sha tags and rollback
  logic as the API image. No Coolify redeploy needed for a scheduled task image (document it in T5 ops doc).
- AC: CI green on the PR; image tags visible in GHCR after merge to `staging`.

## Security

- **Authz:** no new public endpoint. Admin review restricted to staff with explicit permission; delete disabled.
- **Least privilege:** worker has only staging credentials; `staging` role has no access to the main DB.
  App gets staging credentials only for the review UI/import.
- **No secrets in logs or code:** token, keys and DB URLs come from env; log the host, never the URL with password.
- **SSRF:** photo download allow-list (`cdn.mawaqit.net`, https), size and type limits. mawaqit-api has no
  public port.
- **Validation:** coordinates must be in Tunisia's bbox (lat 30–38.5, lon 7–12) or the row is skipped
  with a warning; names truncated to column sizes (already done).
- **Upstream code:** mawaqit-api pinned to a commit SHA; bumping it is a reviewed change.

## Performance

- Crawl: one request for ~2.5k rows; upsert stays row-by-row (fine at this size), single commit.
- Enrich: sequential with delay; ~2.5k rows at 2 s ≈ 1.5 h for a full run, then only stale rows.
  Use `--limit` for first runs.
- Admin: indexes on `status` (exists), `(source, enriched_at)` (new); list paginated (default 100);
  no per-row queries to the main DB in the list view (`matched_masjid_id` shown as a plain id/link).
- Import dedupe: one spatial query per row with `distance_lte` on the indexed `coordinates`; acceptable for
  batches reviewed by hand.

## Legal / risk note (board decision, recorded)

Mawaqit's official API is private; the board chose not to request permission and to use a self-hosted
mawaqit-api. That project's MIT licence covers its code, not Mawaqit's data. Mandatory mitigations:
self-hosted instance only, identifying User-Agent, rate limit (`--delay`), weekly cache, human review before
anything is public, and a kill switch (stop the scheduled tasks). If Mawaqit objects, we stop the jobs and
keep only mosques reviewed and corrected by humans.

## Tests (summary)

- Worker (pytest): adapters (live + file input, archive URL normalisation), migrations runner, crawl
  source defaults and exit codes, enrich (success / 404 / retry / timeout / selection), dedupe (existing).
- Django: router + unmanaged model never migrated, admin actions and permissions, transitions, import
  service (slug, flags, photo rules, dry-run, duplicate by slug), `Masjid.mawaqit_slug` migration.
- Failure cases are required, not optional: unreachable mawaqit-api, bad JSON input, missing env vars,
  forbidden status transition, photo download failure.

## Out of scope / follow-ups

1. Prayer times from meteo.tn (new issue; `PrayerTime` already supports location-based times linked to masjids).
2. Exposing `mawaqit_slug` or source attribution in the public API.
3. Google Places (needs a decision on Google's storage terms).
4. Merging `staging` into `main` / reconciling the two branches (owned by the release process, not this issue).
