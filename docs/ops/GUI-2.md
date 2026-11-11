# GUI-2 — Automatic Coolify deploy from GitHub Actions

## What changed
- `.github/workflows/ci.yml` (new): jobs `lint`, `test`, `docker-build`, `dependency-audit`, `secret-scan`. Runs on `feature/**`/`hotfix/**` pushes and PRs to `staging`/`main`. No deploy, no deploy secrets.
- `.github/workflows/deploy.yml` (new): push to `staging` → env `staging`; push to `main` → env `production` (owner approval). Builds, pushes `ghcr.io/guirat/nasjod-api:<staging|prod>` and `:<full SHA>`, then calls the Coolify webhook.
- `.github/workflows/ci-cd.yml`: SSH deploy, `:latest` push and PR trigger removed. Only the version-bump/release job remains (owner decision pending), actions pinned, secrets moved to `env:`.

## Secrets and environments (names only)
| Where | Name |
|---|---|
| Repo secret | `COOLIFY_TOKEN` |
| Environment `staging` secret | `COOLIFY_WEBHOOK` |
| Environment `production` secret | `COOLIFY_WEBHOOK` (+ required reviewer = owner) |
| Existing, used by `ci-cd.yml` only | `GHCR_PAT`, `GIT_USER_EMAIL`, `GIT_USER_NAME` |
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
3. **Version bump pushes to `main`**: incompatible with "no direct push". Recommendation: delete the `create-release` job and derive versions from tags created manually or by a release workflow run on `workflow_dispatch` with a bypass-free flow; the image is already identified by SHA. Until then, either keep `main` protection with admin/GitHub-Actions bypass for that push, or remove the job. `deploy.yml` skips commits starting with `Update version.txt`, so it works either way.
4. **GHCR visibility**: if the package is private, the Coolify server needs a registry login (PAT with `read:packages`) configured in Coolify.

## Risks
- Single VPS. Webhook failure (non-2xx) fails the job; the old image keeps running.
- `lint` job runs flake8 with only error-class rules (E9,F63,F7,F82); full flake8 not enforced until the legacy code is cleaned.
- Tests need PostGIS; CI uses a `postgis/postgis:16-3.4` service. Not run yet on GitHub.
