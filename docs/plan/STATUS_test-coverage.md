# Status: Test coverage (Phase 2)

Plan: [PLAN_test-coverage.md](PLAN_test-coverage.md). Branch: `agent-test-coverage` (from `develop/main`), worktree `..\find_artek_agent-test-coverage`.

## Now

T2 (empty database, FA-R14): implementer, in the worktree.

## Done

- T1 2026-11-20: `manage.py test` with no labels runs the whole suite (316 tests, OK, 1 skipped = the `/find` prefix test); old `tests.py`, stubs and `app-main/test_*.py` removed; shared helpers in `publications/test_factories.py`; CLAUDE.md, validate skill, `datatransfer_script.sh` updated (`f02e5ea`).
- T0 2026-11-20: worktree and branch `agent-test-coverage` from `develop/main` (`3d69785`), `.dev.env` copied.
- 2026-11-19: decision: `publications/tests.py` and the `app-main/test_*.py` scripts are deleted; their intent is re-covered with fixture tests.

## Open questions

- Coverage target per app and per critical module: set after the T4 baseline.

## Notes for the next session

- Dev stack from the worktree: add `-p find_artek_develop` to the compose command (the project name otherwise comes from the directory and the container names clash). A failed run left unused volumes `find_artek_agent-test-coverage_staticfiles_data`, `..._media_data` and network `find_artek_agent-test-coverage_docker_default`; remove them yourself if you like (`docker volume rm`, `docker network rm`).
- `tests/run.sh` header comment (line 55) still describes the old `tests.py`; T9 rewrites it.
- `develop/main` now has the thumbnail fix (`4f45f6d`, new label `publications.test_report_thumbnail_link` in `tests/run.sh`): merge `develop/main` into `agent-test-coverage` before T9 / before the fast-forward.
