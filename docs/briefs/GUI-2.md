# GUI-2 — Automatic deploy to Coolify from GitHub Actions

## Need (restated)
- Merge to `staging` → build, push and redeploy the Coolify staging app automatically.
- Merge to `main` → same, but only after manual approval in the GitHub Environment `production`.
- Feature branches and PRs run CI only. No more manual redeploy from Coolify.

## Context
- Repo: `guirat/nasjod-api` (Django 5 + DRF + PostGIS, Dockerfile at repo root).
- Registry: **GHCR assumed** (`ghcr.io/guirat/nasjod-api`), since the current workflow already pushes there. Owner to confirm.
- Coolify resources are of type Docker Image. Owner configures Coolify, the API token, webhook URLs and all GitHub secrets.
- Current state: `.github/workflows/ci-cd.yml` runs on push/PR to `main`. It auto-commits a version bump straight to `main`, pushes `:latest` to GHCR, and deploys via SSH + `docker compose`. Lint/test job is commented out. No `staging` branch exists on the remote.

## Owner
DevOps. Security Auditor reviews before anything is merged to `main`. Backend Tech Lead only if the Dockerfile or the test setup needs a change.

## User stories
- As the owner, I merge a PR into `staging` and the staging app runs the new image a few minutes later, with no action in Coolify.
- As the owner, I merge into `main`, GitHub asks me to approve, and production updates only after I approve.
- As the owner, if something breaks I can redeploy a previous build by its SHA tag.

## Scope
1. `.github/workflows/deploy.yml`, on push to `staging` and `main`:
   - Log in to GHCR with `GITHUB_TOKEN`, build, push two tags: env tag (`staging` / `prod`) and the full commit SHA.
   - Deploy job uses GitHub Environment `staging` or `production` (so `secrets.COOLIFY_WEBHOOK` resolves per environment).
   - Call the webhook with `curl --fail` and `Authorization: Bearer $COOLIFY_TOKEN`. Secrets passed through `env:`, never interpolated into the `run:` script.
2. CI workflow on `feature/*` pushes and PRs to `staging`/`main`: lint (flake8), tests (pytest with a PostGIS service container), Docker build without push, dependency audit (e.g. pip-audit), secret scan (e.g. gitleaks). No deploy and no deploy secrets.
3. `production` environment with required reviewer = owner. `main` deploy job pauses until approved.
4. All actions pinned (full commit SHA preferred, with version comment). Minimal `permissions:` at workflow level (`contents: read`), `packages: write` only on the build job.
5. Exact branch protection settings for `staging` and `main` (PR required, required checks named exactly as the CI job names, no force-push, no direct push, include administrators decision flagged).
6. `docs/ops/GUI-2.md`: workflow explained, secret and environment names to create, rollback procedure (redeploy previous SHA tag), how to verify a deploy.
7. Retire the old `ci-cd.yml` deploy path (SSH deploy and `:latest` push) so there is a single deploy path. See open point 3 for the version-bump job.

## Fixed names (use exactly)
- Repo secret `COOLIFY_TOKEN`
- Environment secret `COOLIFY_WEBHOOK` in Environments `staging` and `production`
- GHCR: `GITHUB_TOKEN` (no PAT needed for push from the same repo)

## Acceptance criteria
- [ ] Merge to `staging` triggers build, push and Coolify redeploy with no manual action. Verified on the real staging app (deployed SHA visible).
- [ ] Merge to `main` waits for owner approval in GitHub, then deploys to production.
- [ ] A failing build, or a webhook rejected by Coolify (non-2xx), fails the workflow visibly.
- [ ] Pushes to `feature/*` and PRs run CI only, never deploy.
- [ ] No secret in the repo, in the workflow file, or in logs.
- [ ] Rollback documented and tested once on staging.
- [ ] All actions pinned, minimal permissions.
- [ ] Security Auditor verdict APPROVED on workflows and permissions.

## Out of scope
- Coolify configuration (owner).
- App code changes; Dockerfile changes unless required (then via Backend Tech Lead).
- Migrating to a Git-based build pack.

## Open points to flag to the owner
1. Can GitHub-hosted runners reach the Coolify URL (IP allowlist, firewall)? If not: allow the webhook path, VPN (e.g. Tailscale action), or a self-hosted runner.
2. Tag strategy vs Coolify resource: if the resource tracks a fixed tag (`staging`/`prod`), the webhook redeploy re-pulls it. Rollback by SHA then means re-tagging the old SHA as `staging`/`prod` (or changing the tag in Coolify). DevOps to propose the cleanest option.
3. The current version-bump job pushes commits to `main` directly. That conflicts with "no direct push" protection. Owner decision needed (see issue thread).
4. Is the GHCR package private? If yes, the Coolify server needs pull credentials for GHCR.
