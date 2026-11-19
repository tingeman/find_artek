# Status: Confidential and unverified reports (FA-R75, FA-R30)

Plan: [PLAN_confidential.md](PLAN_confidential.md). Branch: `agent-confidential` (from `develop/main`), worktree `..\find_artek_agent-confidential` (copy of `.dev.env` in it).

## Now

T4 (form) with an implementer in the worktree (uses the dev stack); T5 (media view) in parallel with a second implementer in a detached worktree `..\find_artek_agent-confidential-t5` (no branch; validated with the image gate only; its diff is applied to `agent-confidential`, then that worktree is removed). T6 written and its tests pass (236 with the gate labels), **not committed**: waits for your browser check of logout (see Notes). Release after `2026.3`.

## Done

- 2026-11-19: plan approved. T0: worktree `..\find_artek_agent-confidential` on `agent-confidential` from `develop/main` (`a9844c7`).
- T1 2026-11-19: `Publication.confidential`, migration 0004 (flag from the comment, comment unchanged); `test_roles.RegistrationGroupsMigrationTests` changed deliberately to a `TransactionTestCase` (migrating back past 0004's DDL fails inside a transaction on MariaDB), assertions unchanged; gate 22/22, 231 tests (`a8b3d8b`).
- T2 2026-11-19: `visibility.py` rule (anonymous: verified and not confidential; logged in: not confidential or listed; `artek_editor`/superuser all; features: no report or one visible), `VIEW` in `user_may`; API report list/detail (FA-R76 fixed, invalid `q` 400), features, `confidential` in the serializer; API visibility tests changed deliberately (field instead of comment; listed users and editors see confidential); 263 tests, gate 22/22 (`2c23899`).
- T3 2026-11-19: `ReportView`/`FeatureView` on `PermissionMixin` with `VIEW` (hidden: anonymous → login, logged in → 404); visible features/reports only; Confidential badge; feature file/image links fixed; `test_report_access` hidden-report test changed deliberately (login redirect instead of `access_denied.html`); 273 tests, gate 22/22 (`6f9b5d2`).
- Not done, found in T2: `/api/person/` still lists persons who appear only on hidden reports (names only; plan assumption); `/api/feature/?publication_id=abc` gives 500 (old bug, Phase 2).
- 2026-11-19: decisions: keep `/find/media/` URLs, nginx proxies them to a checked Django view with X-Accel-Redirect; features with no report stay public; anyone who may edit a report may set `confidential`.

## Open questions

- The dev database doesn't have migration 0004: with the worktree's code, report pages give 500 in the dev stack. Migrating the dev DB adds the column and flags 2 rows; afterwards the `develop/main` code can't insert reports there (NOT NULL column it doesn't know) until `migrate publications 0003`. Your call.
- Anonymous users can tell a hidden report (302 to login) from a missing one (404); logged-in users can't. Acceptable, or send anonymous users to the login for unknown ids too?

## Notes for the next session

- T6 (uncommitted in the worktree: `context_processors.py` `AUTH_MARKER`, `settings.py`, `base.html` inline script in the head, `test_auth_marker.py`; label `publications.test_auth_marker` still to add to `tests/run.sh`). Browser check at `http://localhost:8098/` (stack runs from the worktree): open the reports page logged in, devtools → Application → Session Storage shows `reportData*` and `authMarker`; log out, open the reports page: the `reportData*` keys are new (cleared and refetched) and `authMarker` is `anon`.
- Phase 2 idea from T1: a shared helper for migration tests (a `TransactionTestCase` that always restores the latest migrations), so each new schema migration doesn't break older migration tests.

- Runs before [PLAN_test-coverage.md](PLAN_test-coverage.md): both touch `api/views.py`, `tests/run.sh` and the test modules.
