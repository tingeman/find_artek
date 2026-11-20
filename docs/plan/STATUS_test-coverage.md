# Status: Test coverage (Phase 2)

Plan: [PLAN_test-coverage.md](PLAN_test-coverage.md). Branch: `agent-test-coverage` (from `develop/main`), worktree `..\find_artek_agent-test-coverage`.

## Now

T4 (coverage measurement, FA-R44): implementer, in the worktree; then you set the coverage target from the baseline.

## Done

- T3 2026-11-20: `USE_LDAP` from env (`find_artek/env.py` `env_bool`; unset/empty = true, invalid value = `ImproperlyConfigured`); bug fixed: `utils_person` imported `find_artek.settings` directly, so `override_settings`/dev settings were ignored (now `django.conf.settings`); all LDAP uses checked, all guarded; `test_ldap_setting`, `test_import_ldap_off` (16 tests); suite 337 OK, 1 skipped; image tests 22/22 (implementer run) (`1e785df`).
- T2 2026-11-20: `check` and `migrate` pass on an empty DB; Swagger topic list built lazily (drf-yasg renders `lazy` strings, list now current per request); `api.test_empty_database` (5 tests); `tests/run.sh` runs `check` on the empty MariaDB, no `--skip-checks`; suite 321 OK, 1 skipped; image tests 22/22 (implementer run) (`36abed0`).
- T1 2026-11-20: `manage.py test` with no labels runs the whole suite (316 tests, OK, 1 skipped = the `/find` prefix test); old `tests.py`, stubs and `app-main/test_*.py` removed; shared helpers in `publications/test_factories.py`; CLAUDE.md, validate skill, `datatransfer_script.sh` updated (`f02e5ea`).
- T0 2026-11-20: worktree and branch `agent-test-coverage` from `develop/main` (`3d69785`), `.dev.env` copied.
- 2026-11-19: decision: `publications/tests.py` and the `app-main/test_*.py` scripts are deleted; their intent is re-covered with fixture tests.

## Open questions

- Coverage target per app and per critical module: set after the T4 baseline.

## Notes for the next session

- Found in T3, for T7 (person matching): with LDAP on, `utils_person.get_from_studynumber`/`get_from_initials` call `get_or_create_person_from_ldap(person=...)`, but the parameter is `ldap_object` (TypeError on any LDAP hit; reached only via `get_person_from_string`). `register_from_file.py` study-number warning with LDAP on uses `{0}` instead of `{2}` ("add Author manually"; cosmetic).
- `USE_LDAP` for web_server: optional, default `true`; list it in the release USER_STEPS (T10).
- Dev stack from the worktree: add `-p find_artek_develop` to the compose command (the project name otherwise comes from the directory and the container names clash). A failed run left unused volumes `find_artek_agent-test-coverage_staticfiles_data`, `..._media_data` and network `find_artek_agent-test-coverage_docker_default`; remove them yourself if you like (`docker volume rm`, `docker network rm`).
- `tests/run.sh` header comment (line 55) still describes the old `tests.py`; T9 rewrites it.
- `develop/main` now has the thumbnail fix (`4f45f6d`, new label `publications.test_report_thumbnail_link` in `tests/run.sh`): merge `develop/main` into `agent-test-coverage` before T9 / before the fast-forward.
