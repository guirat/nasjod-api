# Status

| Task | Stage | Owner | Status | Notes |
|------|-------|-------|--------|-------|
| GUI-2 Coolify auto-deploy | Implementation (GUI-3) | DevOps | blocked | PR #1 → `staging` open. Owner setup done. `lint` (fixed 855c023), `secret-scan` green; `test`, `dependency-audit` fail → GUI-5. Release job is tag-only (done). |
| GUI-2 Coolify auto-deploy | CI fixes (GUI-5) | Backend Tech Lead | blocked | All 5 PR #1 checks green. Blocked on GUI-6: `masjid/serializers.py:109-110` still sets `is_active=True` for non-admin creates (TL round-2 blocker). Needs fix + TL round 3. |
| GUI-2 Coolify auto-deploy | Staging verification (GUI-3) | DevOps | blocked | After PR #1 green + merged: deploy, rollback, rejected webhook |
| GUI-2 Coolify auto-deploy | Security review (GUI-4) | Security Audit | blocked | Waits for GUI-3 done + staging verified |
| GUI-2 Coolify auto-deploy | Prod release | Owner approval | todo | Needs Security APPROVED + explicit owner OK |
| GUI-8 Root URLs (drop /api/) | Implementation (GUI-9) | Backend Developer → Backend Tech Lead | in progress | Pushed; 5 CI checks green on 9d30e27. Open: `makemigrations --check --dry-run` output, TL review (GUI-9 stuck `blocked`, TL to move to `in_review`). |
| GUI-8 Root URLs (drop /api/) | Split off PR #1 (GUI-8) | Backend Tech Lead → Backend Developer | in progress | Owner chose split. Move 2ec7096/526e5a8/9d30e27 to `feature/GUI-8-root-urls` (stacked PR), remove from PR #1 branch before GUI-6 fix lands. |
| GUI-8 Root URLs (drop /api/) | Frontend base URL (GUI-13) | Frontend Tech Lead | todo | Owner chose Frontend TL. env.development / env.production / src/utils/api.ts → root. Hold merge; ships with backend GUI-8 PR. |
| GUI-8 Root URLs (drop /api/) | Coolify health check (GUI-12) | DevOps | blocked | Switch /api/version/ → /version/ in the same deploy as GUI-8, not before. |
| GUI-16 `:latest` image tag | Push + review + merge to staging (GUI-18) | DevOps → Backend Tech Lead | done | PRs #2/#3/#4 merged to staging (TL APPROVED: GUI-20, GUI-21). Staging Deploy run 43779140092 green; pushed `:staging` + `:<sha>` only, no `:latest`. `:latest` first appears on next prod release (gated). |
| GUI-15 Missing GHCR image | Re-run Coolify deploy job | DevOps | in progress | Root cause: Coolify deploy endpoint now requires POST (405). Fixed by PR #4; run 43779140092 green. DevOps to confirm image in GHCR and close. |
| GUI-8 Root URLs (drop /api/) | Release | Owner approval | todo | Separate release after PR #1. Backend PR + GUI-13 + GUI-12 together; then staging → QA → Security → owner OK. |

Decisions: registry = GHCR `ghcr.io/guirat/nasjod-api` with `GITHUB_TOKEN`; releases = git tags + GitHub Release only (no version.txt commits).
