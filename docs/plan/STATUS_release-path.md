# Status: Release path and pinning (Phase 1)

Plan: [PLAN_release-path.md](PLAN_release-path.md). Branch: `agent-release-path` (from `develop/main`; worktree `..\find_artek_agent-release-path`, with a copy of `.dev.env`). From here on, plan and status changes are committed on this branch, together with the task they belong to.

## Now

T3 (Dockerfile with stages) with `implementer`; then T4, T6. Waiting on you: open points P1–P7 of the draft guide `docs/quick-guides/01_sync_dev_db_from_prod.md`, then T0 and the guide (same SSH session). T2's lock and T5's digests need T0's output.

## Done

- 2026-11-16: roadmap with phases written (`docs/roadmap.md`), Phase 1 planned and approved. Decisions: phase order 1→2→3→4; release 2026.1 = production's code and packages; lock from production's `pip freeze`; cron aligned with monitoring_db (sudo kept, gosu noted as a cross-repo option under FA-R24).
- 2026-11-16: `agent-roadmap` branch and worktree deleted (superseded by `docs/roadmap.md`). Worktree for `agent-release-path` created.
- T1 2026-11-16: baseline against a throwaway MariaDB (no dev DB needed, no secrets): `check` and `makemigrations --check` pass **after** `migrate --skip-checks`; no Django test runs (see notes). Dev DB from production is still wanted for manual testing (guide).

## Open questions

- Is cron/thumbnail generation actually working in production? Code reading says no (T0 confirms).
- `master` reset to the first release tag (FA5, A6): your decision at T9.
- Base image: provisional `python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df` (latest 3.12 on bookworm, 2026-11-16). T0 (`python -V`, `/etc/debian_version`) decides whether production's exact patch or Debian release differs (A1).

## Notes for the next session

- **Baseline findings (T1):**
  - `api/views.py:33-46` queries `Topic` at import time (Swagger description), so `check`, `migrate` and the test runner fail on an empty database: a fresh install can't be migrated without `--skip-checks`, and the API docs' topic list is frozen at process start. Not fixed in 2026.1 (no code changes); `tests/run.sh` migrates with `--skip-checks` first. Roadmap FA-R14.
  - The committed suite doesn't run: `publications/tests.py:9` imports `utils.get_all_publications`, which doesn't exist; discovery also picks up the ad-hoc `app-main/test_file_upload.py` (imports `publications.utils`, only in your uncommitted work). So the release gate in 2026.1 has **no Django tests** (A4); Phase 2 builds the suite.
  - Shell scripts are checked out with CRLF on Windows (`core.autocrlf=true`, no `.gitattributes`), so an image built from a Windows checkout has a broken entrypoint (`exec ... no such file or directory`). Production builds on Linux and is not affected; the release build runs in WSL. Fixed in T3 with `.gitattributes`.
- Baseline script (scratchpad, not in the repo): migrate, check, makemigrations, test against `mariadb:11.2` on an internal network with generated credentials. T6 turns this into `tests/run.sh`.
- web_server `docs/plan/USER_TASKS.md:158` still asks to merge `agent-roadmap`; it should be updated in that repo (the branch is gone, its content is in `docs/roadmap.md`).
- Your uncommitted person-disambiguation work is in the main checkout on `develop/main`. Phase 1 works in the separate worktree.
