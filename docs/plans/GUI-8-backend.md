# GUI-8 Backend plan: serve the API at the root (drop `/api/` prefix)

Owner: Backend Tech Lead. Implementer: Backend Developer.
Branch: `feature/GUI-2-coolify-deploy` (shared with GUI-7 run; commit small, pull/rebase before push).

## Approach

User decision (GUI-7): the API is served at `https://api.nasjod.com/` root. No `/api/` alias,
no redirect. Breaking change accepted; clients are updated by the user.

Only `nasjod/nasjod/urls.py` changes routes. All tests use `reverse()` by URL name, so they keep
working without path edits. URL names do not change.

## API contract (breaking: path change only)

Every path loses its `/api` prefix. Methods, request/response bodies, status codes, auth (JWT
Bearer via `/auth/token/`) and error format are unchanged.

| Old                          | New                      | Name                  |
|------------------------------|--------------------------|-----------------------|
| `/api/auth/token/`           | `/auth/token/`           | `token_obtain_pair`   |
| `/api/auth/token/refresh/`   | `/auth/token/refresh/`   | `token_refresh`       |
| `/api/masajid/...`           | `/masajid/...`           | `masjid-list/detail`  |
| `/api/suggestions-modification-masjid/...` | `/suggestions-modification-masjid/...` | `suggestion-modification-masjid-*` |
| `/api/prayer-times/...`, `/api/jumuah-prayer-times/...`, `/api/iqamas/...`, `/api/eid-prayer-times/...` | same without `/api` | unchanged |
| `/api/users/...`             | `/users/...`             | `user-list/detail`    |
| `/api/contributors/`         | `/contributors/`         | `user-contributors`   |
| `/api/schema/`               | `/schema/`               | `schema`              |
| `/api/schema/swagger-ui/`    | `/schema/swagger-ui/`    | `swagger-ui`          |
| `/api/schema/redoc/`         | `/schema/redoc/`         | `redoc`               |
| `/api/version/`              | `/version/`              | `version`             |
| `/admin/`                    | `/admin/` (unchanged)    |                       |
| `/` (was 404)                | `/` -> 200, DRF API root of the masjid `DefaultRouter` | `api-root` |
| `/api/...` (any)             | 404                      |                       |

Note on `/`: `masjid.urls` uses `DefaultRouter`, which adds an API root view at its mount
point. Mounted at `""`, it now answers `GET /` with 200 JSON listing `masajid` and
`suggestions-modification-masjid` (AllowAny, read-only). This is the intended fix for the
GUI-7 root 404. It is acceptable that it does not list every endpoint.

Collision check (done by TL, developer must confirm with tests):
- Router prefixes (`masajid`, `suggestions-modification-masjid`), prayertime paths, `auth/`,
  `users/`, `contributors/`, `schema/`, `version/` are all distinct and none equals `admin/`
  or `static/` (WhiteNoise, `STATIC_URL=/static/`).
- `users/` router registers prefix `''` but is nested under `users/`, so no root collision.
- Ordering: keep `admin/` first.

## Data model / migrations

None. Run `python manage.py makemigrations --check --dry-run` to confirm.

## Tasks (in order)

1. `nasjod/nasjod/urls.py`: remove the `api/` prefix from every route exactly per the table.
   `path("api/", include(...))` becomes `path("", include(...))`. Keep `admin/` unchanged and
   first. Do not add any `/api/` alias or redirect. Do not rename any URL name.
   - AC: `python manage.py show_urls` (or `django.urls.get_resolver` dump) shows no `api/` prefix.
2. Search the repo (excluding `.paperclip-repositories/`, `venv/`) for hardcoded `/api/` paths:
   settings, `README.md`, `IMPORT_MOSQUES_README.md`, `scripts/`, `Dockerfile`,
   `docker-compose*.yml`, `docs/ops/`. Update backend-owned references (e.g. healthchecks, curl
   examples). Do NOT edit the frontend repo or Coolify config; list them in your handoff.
   - AC: `grep -rn "/api/" --exclude-dir=venv --exclude-dir=.paperclip-repositories --exclude-dir=.git .`
     returns only intentional hits (e.g. this plan, history docs), each justified in the handoff.
3. Add tests in a new `nasjod/core/tests/test_urls.py` (pytest, `api_client` fixture):
   - `reverse('version') == '/version/'` and `GET /version/` -> 200 with `version` key.
   - `GET /` -> 200 (API root).
   - `GET /api/version/` -> 404 and `GET /api/masajid/` -> 404 (no alias).
   - `reverse()` for `schema`, `token_obtain_pair`, `masjid-list`, `user-list`,
     `user-contributors`, `prayer-time-list` return the new unprefixed paths.
   - `GET /schema/` -> 200 and generated OpenAPI `paths` contain no key starting with `/api/`.
   - `GET /admin/` still resolves to the admin (302 to login).
4. Run the full suite (`pytest` from `nasjod/`), plus `makemigrations --check --dry-run`.
   All green. Commit with message prefix `GUI-8:`; push.

## Security and performance

- No authz change. Do not touch permission classes or authentication settings.
- `GET /` exposes only the router's link listing (already public under `/api/`). No new data.
- Swagger/Redoc remain at the same exposure level as before; only path changes.
- No queries added; no performance impact.

## Handoff

Comment on GUI-8 with: commit SHA, test output summary, list of external places still using
`/api/` (frontend `env.*`, `src/utils/api.ts` default, Coolify health check `/api/version/` ->
`/version/`). Then reassign to Backend Tech Lead for review.
