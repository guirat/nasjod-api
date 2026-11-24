# GUI-2 — Automatic Coolify deploy from GitHub Actions

## What changed
- `.github/workflows/ci.yml` (new): jobs `lint`, `test`, `docker-build`, `dependency-audit`, `secret-scan`. Runs on `feature/**`/`hotfix/**` pushes and PRs to `staging`/`main`. No deploy, no deploy secrets.
- `.github/workflows/deploy.yml` (new): push to `staging` → env `staging`; push to `main` → env `production` (owner approval). Job `image` builds and pushes only the immutable `ghcr.io/guirat/nasjod-api:<full SHA>`. Job `deploy` (environment-gated, the only other job with `packages: write`) then moves `:staging` / `:prod` (and `:latest` on prod) to that SHA and calls the Coolify webhook.
- `.github/workflows/ci-cd.yml`: SSH deploy, `:latest` push and PR trigger removed. Only the tag-and-release job remains (owner decision 2026-11-11: tag-only), actions pinned, secrets moved to `env:`.

## Secrets and environments (names only)
| Where | Name |
|---|---|
| Environment `staging` secret | `COOLIFY_WEBHOOK`, `COOLIFY_TOKEN` |
| Environment `production` secret | `COOLIFY_WEBHOOK`, `COOLIFY_TOKEN` (+ required reviewer = owner) |
| Repo secret `COOLIFY_TOKEN` | **delete** (security finding M1) |
| Obsolete after this change (delete) | `GHCR_PAT`, `GIT_USER_EMAIL`, `GIT_USER_NAME` |
| To delete after merge | `VPS_SSH_PRIVATE_KEY`, `VPS_SSH_HOST`, `VPS_SSH_USER` |

**Owner steps for M1 (the agent never reads or sets these values):**
1. In Coolify, create two API tokens with deploy-only permission (one for staging, one for production). Revoke the old shared token afterwards.
2. GitHub → Settings → Environments → `staging` → add secret `COOLIFY_TOKEN` (staging token). Same in `production` with the production token.
3. GitHub → Settings → Secrets and variables → Actions → delete the repo-level `COOLIFY_TOKEN`.
The workflow needs no change for this: `secrets.COOLIFY_TOKEN` in the `deploy` job resolves to the environment secret.

`COOLIFY_WEBHOOK` is the full Coolify deploy URL for that resource. Push to GHCR uses `GITHUB_TOKEN`.

## Tag strategy
Coolify resources track the moving tags `staging` / `prod`. Every build gets an immutable `:<full SHA>` tag, pushed before the gate. The moving tags only change inside the gated `deploy` job (so a production approval is what moves `:prod` / `:latest`), then the webhook redeploys and re-pulls the env tag. The webhook call uses `--proto '=https' --proto-redir '=https'`.

## Verify a deploy
1. Actions → Deploy run is green; job summary shows the SHA.
2. `docker inspect <container> --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}'` on the VPS (or the image tag shown in Coolify) equals the merged commit SHA.
3. App health endpoint responds.

## Rollback
Actions → Deploy → Run workflow, choose branch `staging` (or `main`), set `rollback_sha` to the full SHA of a previously built image. The `image` job only computes tags (no build). The gated `deploy` job re-tags that image as the env tag (no rebuild; fails if the SHA image does not exist) and calls the webhook. Production rollback pauses for approval in `production` before any tag moves.

### Rollback verification (GUI-32)
Coolify answers `200 "Deployment already queued for this commit."` and starts nothing while a deployment is queued/running for the resource, so a rollback right after a push can be swallowed. The deploy step therefore: triggers, and if the answer is "already queued" waits until `GET /api/v1/deployments` shows nothing in flight for the resource, then triggers again and polls `GET /api/v1/deployments/<uuid>` until `finished` (fails on `failed`, any unreadable status, timeout, or if still deduplicated). The step has a 25 min timeout. Deployment logs are never printed (public repo). To prove the running image, compare the image revision label on the VPS/Coolify with `docker buildx imagetools inspect ghcr.io/guirat/nasjod-api:<sha>`.
**Known limit:** the in-flight filter in `wait_idle` probably does not match per resource (list items carry `application_id`/`application_name`, not a uuid), so it counts every in-flight deployment on the Coolify instance. That only waits longer, but a concurrent deploy of another app can hit the 10 min wait and fail the rollback; rerun it. Optional follow-up: filter on `application_name`.
**Token scope:** `COOLIFY_TOKEN` needs `read` (plus `deploy`) so the job can verify. With a deploy-only token the job prints `accepted (NOT verified: COOLIFY_TOKEN lacks read scope)`, never "finished".

## Open points
1. **Runner → Coolify reachability**: GitHub-hosted runner IPs are not fixed. If Coolify is behind a firewall/allowlist, allow 443 to the Coolify API path, or use Tailscale/self-hosted runner.
2. **Tag strategy**: see above; rollback by re-tag via `workflow_dispatch`.
3. **Version bump (closed, owner decision 2026-11-11: tag-only)**: `create-release` (`ci-cd.yml`, push to `main`) computes the next semver from the latest `v*` tag, then creates the tag on the merge commit SHA and a GitHub Release through the API. It uses `GITHUB_TOKEN` with `contents: write` on that job only, and never pushes to a branch, so no branch protection bypass is needed. `version.txt` is no longer updated: it is frozen at `2.2.32`. **Flag:** `nasjod/core/views.py` (`version` view) reads `version.txt` at runtime, so the version endpoint will keep returning `2.2.32`. App change needed to read the version from the image/tag (e.g. build arg); routed to the Manager/Backend TL.
4. **GHCR visibility**: if the package is private, the Coolify server needs a registry login (PAT with `read:packages`) configured in Coolify.

## Risks
- Tool pins: `semver==3.1.2` is installed with `--require-hashes`; `pip-audit==2.10.1` is pinned by version only (hash-pinning its transitive tree needs a lock file; follow-up if wanted).
- Single VPS. Webhook failure (non-2xx) fails the job; the old image keeps running.
- `lint` job runs flake8 with only error-class rules (E9,F63,F7,F82); full flake8 not enforced until the legacy code is cleaned.
- Tests need PostGIS; CI uses a `postgis/postgis:16-3.4` service. Not run yet on GitHub.

## Releases
Git tag `vX.Y.Z` plus GitHub Release on each merge to `main`, created by `ci-cd.yml`. Bump: `feat!` in the commit message = major, `feat` = minor, otherwise patch. No workflow writes to any branch. Tags created with `GITHUB_TOKEN` do not trigger other workflows (deploy runs from the push to `main`).

## Branch protection note
With no workflow pushing to branches, set **Include administrators = ON** on `staging` and `main`, with no bypass exception.
