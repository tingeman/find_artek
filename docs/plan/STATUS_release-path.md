# Status: Release path and pinning (Phase 1)

Plan: [PLAN_release-path.md](PLAN_release-path.md). Branch: `agent-release-path` (not created yet; worktree `..\find_artek_agent-release-path`).

## Now

Plan is a draft, waiting for your approval. After that: T0 (you, read-only commands on the host, listed in the plan), and in parallel T1 (worktree and test baseline, orchestrator).

## Done

- 2026-11-16: roadmap with phases written (`docs/roadmap.md`), Phase 1 planned. Decisions: phase order 1→2→3→4; release 2026.1 = production's code and packages; lock from production's `pip freeze`; cron aligned with monitoring_db (sudo kept, gosu noted as a cross-repo option under FA-R24).

## Open questions

- Is cron/thumbnail generation actually working in production? Code reading says no (T0 confirms).
- `master` reset to the first release tag (FA5, A6): your decision at T9.

## Notes for the next session

- The roadmap replaces the one on branch `agent-roadmap` (worktree `..\find_artek_agent-roadmap`, 3 unpushed docs commits). That branch can be deleted once you agree; web_server `docs/plan/USER_TASKS.md:158` still asks to merge it and should be updated in that repo.
- Your uncommitted person-disambiguation work is in the main checkout on `develop/main`. Phase 1 works in a separate worktree so it isn't disturbed.
