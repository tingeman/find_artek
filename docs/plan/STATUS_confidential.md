# Status: Confidential and unverified reports (FA-R75, FA-R30)

Plan: [PLAN_confidential.md](PLAN_confidential.md). Branch: `agent-confidential` (from `develop/main`), worktree `..\find_artek_agent-confidential` (copy of `.dev.env` in it).

## Now

T8: `2026.4` tagged (`debfb94`), built (22/22, 316 tests), on the releases share, `releases.yml` updated (not committed). Next: you commit `releases.yml` and deploy, steps 5-9 of [USER_STEPS_2026.4.md](USER_STEPS_2026.4.md).

## Done

- 2026-11-19: plan approved. T0: worktree `..\find_artek_agent-confidential` on `agent-confidential` from `develop/main` (`a9844c7`).
- T1 2026-11-19: `Publication.confidential`, migration 0004 (flag from the comment, comment unchanged); `test_roles.RegistrationGroupsMigrationTests` changed deliberately to a `TransactionTestCase` (migrating back past 0004's DDL fails inside a transaction on MariaDB), assertions unchanged; gate 22/22, 231 tests (`a8b3d8b`).
- T2 2026-11-19: `visibility.py` rule (anonymous: verified and not confidential; logged in: not confidential or listed; `artek_editor`/superuser all; features: no report or one visible), `VIEW` in `user_may`; API report list/detail (FA-R76 fixed, invalid `q` 400), features, `confidential` in the serializer; API visibility tests changed deliberately (field instead of comment; listed users and editors see confidential); 263 tests, gate 22/22 (`2c23899`).
- T3 2026-11-19: `ReportView`/`FeatureView` on `PermissionMixin` with `VIEW` (hidden: anonymous → login, logged in → 404); visible features/reports only; Confidential badge; feature file/image links fixed; `test_report_access` hidden-report test changed deliberately (login redirect instead of `access_denied.html`); 273 tests, gate 22/22 (`6f9b5d2`).
- T4 2026-11-19: `confidential` checkbox in the add/edit form (anyone who may edit), shown on the review step (a change of the flag alone counts as a change), saved in finalize; 8 tests, 281 tests (`5c9f827`).
- T6 2026-11-19: login marker in `base.html` (`anon` or a hash of the session key) and an inline head script that drops `reportData*`/`featureData*` from sessionStorage when it changes; checked by you in the browser; 5 tests (`461a467`).
- T5 2026-11-19: `media_access.py` + `serve_media` for every file under MEDIA_URL (owner lookup, rule, unowned files editors only, traversal and symlinks refused; X-Accel-Redirect to `/find/_protected_media/` in production, FileResponse in dev); command `check_media_access`; review page PDF link fixed; written in a detached worktree in parallel with T3/T4 and applied here; 314 tests, gate 22/22 (`672fe07`).
- T7 2026-11-19: docs (`user-data-and-permissions.md` section, deploy-contract skill: nginx change = add internal `/find/_protected_media/` first, then remove the `/find/media/` alias, in one change; rollback; functional checks), gate list complete (`0269fa7`).
- 2026-11-20: worktree `agent-registration` removed. `develop/main` (2026.3.1 and docs) merged into `agent-confidential` (`0b13b6e`; conflict in `test_roles.py` imports only); check, makemigrations clean, gate 22/22, 316 tests; full suite 318 with the 2 known import errors of the legacy `publications/tests.py` and `app-main/test_file_upload.py` (PLAN_test-coverage deletes them).
- 2026-11-20: dev DB migrated to 0004 again (your OK, stays there). Unowned files (64) reviewed: 35 orphan `FileObject` rows linked to nothing, 13 files with no row (copies, stale thumbnails, a test upload), 16 `ø`/`Ø` names mangled in the dev copy whose DB rows (linked) have the correct name and whose correct file is missing. No unowned file is linked from a page, so default deny hides nothing users can reach today. Deferred: FA-R86 (orphans), FA-R87 (mangled names; check production in step 5).
- 2026-11-20: `develop/main` fast-forwarded to `debfb94` (your OK); tag `2026.4`; bundle tarball_sha256 `8b4c9b73...`; share copy verified; web_server `releases.yml` edited.
- Decision 2026-11-19: anonymous users are redirected to the login for hidden reports (302) while unknown ids give 404; kept.
- Not done, found in T2: `/api/person/` still lists persons who appear only on hidden reports (names only; plan assumption); `/api/feature/?publication_id=abc` gives 500 (old bug, Phase 2).
- 2026-11-19: decisions: keep `/find/media/` URLs, nginx proxies them to a checked Django view with X-Accel-Redirect; features with no report stay public; anyone who may edit a report may set `confidential`.

## Open questions


## Notes for the next session

- Dev DB at 0004 since 2026-11-20 and the dev stack runs from the `agent-confidential` worktree (project `find_artek_develop`). Back to `develop/main` before the merge only if needed: `migrate publications 0003` from the confidential container first.
- History: dev DB migrated to 0004 on 2026-11-19 (your permission): 2 of 494 reports flagged. Reversed to 0003 on 2026-11-19 (from the confidential container) and the dev stack rebuilt from `develop/main`. To run `agent-confidential` again: `migrate` (0004 re-derives the flags from the comments); back to `develop/main`: `migrate publications 0003` from the confidential container first.

- Phase 2 idea from T1: a shared helper for migration tests (a `TransactionTestCase` that always restores the latest migrations), so each new schema migration doesn't break older migration tests.

- Runs before [PLAN_test-coverage.md](PLAN_test-coverage.md): both touch `api/views.py`, `tests/run.sh` and the test modules.
