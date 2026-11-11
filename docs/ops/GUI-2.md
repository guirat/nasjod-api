# GUI-2 — Automatic Coolify deploy from GitHub Actions

## What changed
- `.github/workflows/ci.yml` (new): jobs `lint`, `test`, `docker-build`, `dependency-audit`, `secret-scan`. Runs on `feature/**`/`hotfix/**` pushes and PRs to `staging`/`main`. No deploy, no deploy secrets.
- `.github/workflows/deploy.yml` (new): push to `staging` → env `staging`; push to `main` → env `production` (owner approval). Builds, pushes `ghcr.io/guirat/nasjod-api:<staging|prod>` and `:<full SHA>`, then calls the Coolify webhook.
- `.github/workflows/ci-cd.yml`: SSH deploy, `:latest` push and PR trigger removed. Only the tag-and-release job remains (owner decision 2026-11-11: tag-only), actions pinned, secrets moved to `env:`.

## Secrets and environments (names only)
| Where | Name |
|---|---|
| Repo secret | `COOLIFY_TOKEN` |
| Environment `staging` secret | `COOLIFY_WEBHOOK` |
| Environment `production` secret | `COOLIFY_WEBHOOK` (+ required reviewer = owner) |
| Obsolete after this change (delete): `GHCR_PAT`, `GIT_USER_EMAIL`, `GIT_USER_NAME` |
| To delete after merge | `VPS_SSH_PRIVATE_KEY`, `VPS_SSH_HOST`, `VPS_SSH_USER` |

`COOLIFY_WEBHOOK` is the full Coolify deploy URL for that resource. Push to GHCR uses `GITHUB_TOKEN`.

## Tag strategy
Coolify resources track the moving tags `staging` / `prod`. Every build also gets an immutable `:<full SHA>` tag. A webhook redeploy re-pulls the env tag.

## Verify a deploy
1. Actions → Deploy run is green; job summary shows the SHA.
2. `docker inspect <container> --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}'` on the VPS (or the image tag shown in Coolify) equals the merged commit SHA.
3. App health endpoint responds.

## Rollback
Actions → Deploy → Run workflow, choose branch `staging` (or `main`), set `rollback_sha` to the full SHA of a previously built image. The workflow re-tags that image as the env tag (no rebuild) and calls the webhook. Production rollback still pauses for approval in `production`.

## Open points
1. **Runner → Coolify reachability**: GitHub-hosted runner IPs are not fixed. If Coolify is behind a firewall/allowlist, allow 443 to the Coolify API path, or use Tailscale/self-hosted runner.
2. **Tag strategy**: see above; rollback by re-tag via `workflow_dispatch`.
3. **Version bump (closed, owner decision 2026-11-11: tag-only)**: `create-release` (`ci-cd.yml`, push to `main`) computes the next semver from the latest `v*` tag, then creates the tag on the merge commit SHA and a GitHub Release through the API. It uses `GITHUB_TOKEN` with `contents: write` on that job only, and never pushes to a branch, so no branch protection bypass is needed. `version.txt` is no longer updated: it is frozen at `2.2.32`. **Flag:** `nasjod/core/views.py` (`version` view) reads `version.txt` at runtime, so the version endpoint will keep returning `2.2.32`. App change needed to read the version from the image/tag (e.g. build arg); routed to the Manager/Backend TL.
4. **GHCR visibility**: if the package is private, the Coolify server needs a registry login (PAT with `read:packages`) configured in Coolify.

## Risks
- Single VPS. Webhook failure (non-2xx) fails the job; the old image keeps running.
- `lint` job runs flake8 with only error-class rules (E9,F63,F7,F82); full flake8 not enforced until the legacy code is cleaned.
- Tests need PostGIS; CI uses a `postgis/postgis:16-3.4` service. Not run yet on GitHub.

## Releases
Git tag `vX.Y.Z` plus GitHub Release on each merge to `main`, created by `ci-cd.yml`. Bump: `feat!` in the commit message = major, `feat` = minor, otherwise patch. No workflow writes to any branch. Tags created with `GITHUB_TOKEN` do not trigger other workflows (deploy runs from the push to `main`).

## Branch protection note
With no workflow pushing to branches, set **Include administrators = ON** on `staging` and `main`, with no bypass exception.
