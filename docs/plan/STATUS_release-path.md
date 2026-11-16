# Status: Release path and pinning (Phase 1)

> **This copy is outdated.** The current plan, status and user steps live on branch `agent-release-path`, in the worktree `C:\thin\02_Code\docker_projects\find_artek_agent-release-path\docs\plan\` (`STATUS_release-path.md`, `PLAN_release-path.md`, `USER_STEPS_release-path.md`). They come back to `develop/main` with the merge (T8). Your next manual steps: `USER_STEPS_release-path.md` there, steps 1–3.

Plan: [PLAN_release-path.md](PLAN_release-path.md). Branch: `agent-release-path` (created 2026-11-16 from `develop/main` `4d885fc`; worktree `..\find_artek_agent-release-path`, with a copy of `.dev.env`).

## Now

Plan approved 2026-11-16. T1 is blocked: there is no dev database on the workstation (no volume `find-artek-mariadb-dev`). You chose to copy production's database: the draft guide `docs/quick-guides/01_sync_dev_db_from_prod.md` has open points P1–P7 to settle with you, then you run it. T0 (read-only host commands, in the plan) can be done in the same SSH session as the guide's step 2.

## Done

- 2026-11-16: `agent-roadmap` branch and worktree deleted (superseded by `docs/roadmap.md`). Worktree for `agent-release-path` created; the dev image builds unchanged from it (`Dockerfile.develop`).

- 2026-11-16: roadmap with phases written (`docs/roadmap.md`), Phase 1 planned. Decisions: phase order 1→2→3→4; release 2026.1 = production's code and packages; lock from production's `pip freeze`; cron aligned with monitoring_db (sudo kept, gosu noted as a cross-repo option under FA-R24).

## Open questions

- Is cron/thumbnail generation actually working in production? Code reading says no (T0 confirms).
- `master` reset to the first release tag (FA5, A6): your decision at T9.

## Notes for the next session

- The roadmap replaces the one on branch `agent-roadmap` (worktree `..\find_artek_agent-roadmap`, 3 unpushed docs commits). That branch can be deleted once you agree; web_server `docs/plan/USER_TASKS.md:158` still asks to merge it and should be updated in that repo.
- Your uncommitted person-disambiguation work is in the main checkout on `develop/main`. Phase 1 works in a separate worktree so it isn't disturbed.
