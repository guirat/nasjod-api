# GUI-5 Backend plan: green `test` and `dependency-audit` on PR #1

Owner: Backend Tech Lead. Implementer: Backend Developer.
Branch: `feature/GUI-2-coolify-deploy` (PR #1 -> `staging`). Nothing goes to `main`.

## Approach

Two independent failures, both first-time CI runs of checks that were previously disabled.

1. `test`: pytest collection fails because the masjid tests import prayer-time models from
   `masjid.models`. Since the prayer-time split, `PrayerTime`, `JumuahPrayerTime`,
   `EidPrayerTime` (and `IqamaTime`) live in `prayertime.models`, and `PrayerTime` /
   `EidPrayerTime` now extend `BaseLocatedPrayerTime`. Fixing imports will likely surface
   fixture/field mismatches against the current models. Fix the tests to match the current
   schema; fix app code if a test exposes a real bug.
2. `dependency-audit`: `pip-audit -r requirements.txt` (resolves transitive deps too) reports
   132 vulns in 6 packages. Bump each to the lowest version that clears its advisories, then
   re-run the test suite.

## API contract

No change. No endpoint, schema, status code, or auth changes are in scope. If a dependency bump
(DRF, simplejwt, drf-spectacular, Django) changes any response shape or the generated OpenAPI
schema, stop and report it to me before committing; that is a contract change.

## Data model / migrations

None expected. After any Django/DRF bump run `python manage.py makemigrations --check --dry-run`.
If it reports pending migrations, do not generate them; report to me (that means the bump changed
model state and needs a decision).

## Tasks (in order)

### T1. Fix masjid test imports
- In `nasjod/masjid/tests/conftest.py`, `test_models.py`, `test_endpoint.py`: import `Masjid` from
  `..models` and `PrayerTime`, `JumuahPrayerTime`, `EidPrayerTime` from `prayertime.models`
  (same style as `nasjod/masjid/serializers.py:13`).
- AC: `pytest --collect-only` in `nasjod/` collects all tests with zero errors.

### T2. Make the suite pass for real
- Run the full suite (`cd nasjod && pytest`). For each failure, decide: stale test (update
  fixtures/assertions to the current model/endpoint behavior) or real bug (fix the app code,
  keep the assertion).
- Not allowed: `skip`/`xfail`, deleting tests, deleting or loosening assertions just to pass.
  If a test covers behavior that was intentionally removed, list it in your report with the
  commit that removed the behavior; I decide.
- Local DB: settings use PostGIS. If you cannot run PostGIS locally, push and use the PR #1
  `test` job as the runner (env is in `.github/workflows/ci.yml`, read it, do not edit it).
- AC: `test` job green on PR #1. Report pass count.

### T3. Dependency audit, smallest safe bumps
- In a fresh Python 3.12 venv: `pip install pip-audit && pip-audit -r requirements.txt`.
  Paste the full table (package, version, advisory IDs, fix versions) in your report.
- For each vulnerable package pick the lowest fix version that clears all its advisories.
  Notes / expectations:
  - Django 5.0 is EOL; fixes after 5.0.14 only exist on 5.1/5.2. Prefer the latest **5.2.x LTS**
    (same major). Go through the 5.1 and 5.2 release notes "backwards incompatible changes" and
    check that nothing we use is affected. Django 6.x is out of scope.
  - pillow: stay on 10.x/11.x if that clears it. If only 12.x clears it and tests break, stop.
  - Dev tools (`black`, `pytest`, `flake8`) are in `requirements.txt` and get audited too.
    Bump them as well (black major bumps are fine; it is only a formatter, do NOT reformat code).
    `flake8>=3.9.0,<4.0.1` can move to `flake8>=7,<8` to match the CI lint job. `pytest` and
    `pytest-django` must stay compatible with each other.
  - Transitive vulns (e.g. urllib3, sqlparse, requests, idna): first try bumping the direct
    parent (e.g. boto3). Only if that does not work add an explicit pin with a
    `# security floor, transitive via <parent>` comment.
  - `sentry-sdk[django]` is unpinned; pin it to the version pip resolves today (reproducible
    builds), unless that version is vulnerable.
- Re-run `pip-audit -r requirements.txt` until 0 known vulns, then `makemigrations --check` and
  the full test suite.
- STOP and report (do not commit) if: a package has no fixed version, the only fix is a major
  upgrade that breaks tests or app behavior, or a fix needs code changes beyond trivial
  deprecation renames. Give me package, advisory IDs, fix version, and the concrete risk.
- Not allowed: `--ignore-vuln`, editing the workflow, removing packages we use.
- AC: `dependency-audit` job green on PR #1; tests still green; Docker image still builds
  (`docker-build` job green).

## Security / performance
- No secrets in commits or logs; CI values in the workflow are dummy values, do not copy them
  into settings.
- No raw SQL introduced. No test fixture should require real credentials or network.
- Review Django 5.1/5.2 security-relevant default changes (e.g. password hasher iterations,
  `ALLOWED_HOSTS`/`CSRF` behavior) and mention anything affecting our settings.

## Tests
- Whole suite green under CI PostGIS. Failure cases already in the suite (auth denied,
  validation errors) must remain asserted.
- If T2 required an app-code bug fix, add/keep a test that fails without the fix.

## Git rules (shared workspace with the GUI-2 DevOps run)
- Work on `feature/GUI-2-coolify-deploy`. `git pull --rebase` before every push.
- Commit with explicit paths only (`git add <files>`). Do NOT add `.claude/`, `docs/status.md`,
  or anything under `.github/`.
- Small commits, prefix `GUI-5:` (e.g. `GUI-5: fix masjid test imports`, `GUI-5: bump Django to 5.2.x LTS`).
- No force push.

## Report back (comment on your subtask)
Commits SHAs, full before/after pip-audit table, version changes with rationale, test pass count,
every test you changed and why, CI run links for `test` / `dependency-audit` / `docker-build`.
