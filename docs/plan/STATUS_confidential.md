# Status: Confidential and unverified reports (FA-R75, FA-R30)

Plan: [PLAN_confidential.md](PLAN_confidential.md). Branch: `agent-confidential` (from `develop/main`), worktree `..\find_artek_agent-confidential` (not created yet).

## Now

Plan drafted 2026-11-19, waiting for your approval. Then T0 (worktree, main session) and T1 (implementer). Release after `2026.3`.

## Done

- 2026-11-19: decisions: keep `/find/media/` URLs, nginx proxies them to a checked Django view with X-Accel-Redirect; features with no report stay public; anyone who may edit a report may set `confidential`.

## Open questions

## Notes for the next session

- Runs before [PLAN_test-coverage.md](PLAN_test-coverage.md): both touch `api/views.py`, `tests/run.sh` and the test modules.
