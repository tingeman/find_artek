# Status: Confidential and unverified reports (FA-R75, FA-R30)

Plan: [PLAN_confidential.md](PLAN_confidential.md). Branch: `agent-confidential` (from `develop/main`), worktree `..\find_artek_agent-confidential` (copy of `.dev.env` in it).

## Now

T2 (rule and API) with the implementer. T6 written and its tests pass (236 with the gate labels), **not committed**: waits for your browser check of logout (see Notes). Release after `2026.3`.

## Done

- 2026-11-19: plan approved. T0: worktree `..\find_artek_agent-confidential` on `agent-confidential` from `develop/main` (`a9844c7`).
- T1 2026-11-19: `Publication.confidential`, migration 0004 (flag from the comment, comment unchanged); `test_roles.RegistrationGroupsMigrationTests` changed deliberately to a `TransactionTestCase` (migrating back past 0004's DDL fails inside a transaction on MariaDB), assertions unchanged; gate 22/22, 231 tests (`a8b3d8b`).
- 2026-11-19: decisions: keep `/find/media/` URLs, nginx proxies them to a checked Django view with X-Accel-Redirect; features with no report stay public; anyone who may edit a report may set `confidential`.

## Open questions

## Notes for the next session

- T6 (uncommitted in the worktree: `context_processors.py` `AUTH_MARKER`, `settings.py`, `base.html` inline script in the head, `test_auth_marker.py`; label `publications.test_auth_marker` still to add to `tests/run.sh`). Browser check at `http://localhost:8098/` (stack runs from the worktree): open the reports page logged in, devtools → Application → Session Storage shows `reportData*` and `authMarker`; log out, open the reports page: the `reportData*` keys are new (cleared and refetched) and `authMarker` is `anon`.
- Phase 2 idea from T1: a shared helper for migration tests (a `TransactionTestCase` that always restores the latest migrations), so each new schema migration doesn't break older migration tests.

- Runs before [PLAN_test-coverage.md](PLAN_test-coverage.md): both touch `api/views.py`, `tests/run.sh` and the test modules.
