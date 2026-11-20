# Status: Test coverage (Phase 2)

Plan: [PLAN_test-coverage.md](PLAN_test-coverage.md). Branch: `agent-test-coverage` (from `develop/main`), worktree `..\find_artek_agent-test-coverage`.

## Now

You: set the coverage target from the T4 baseline (open question). Then T5 (URL smoke tests): implementer, in the worktree.

## Done

- T4 2026-11-20: `coverage` 7.16.2 dev-only (`requirements-dev.in`/lock, production lock unchanged, not in the production image), `app-main/.coveragerc` (branch on, `include_namespace_packages` because `management/commands/` has no `__init__.py`), readme/CLAUDE.md/validate skill; suite 337 OK, 1 skipped; image `--quick` 12/12 (`e21318d`). Baseline below.
- T3 2026-11-20: `USE_LDAP` from env (`find_artek/env.py` `env_bool`; unset/empty = true, invalid value = `ImproperlyConfigured`); bug fixed: `utils_person` imported `find_artek.settings` directly, so `override_settings`/dev settings were ignored (now `django.conf.settings`); all LDAP uses checked, all guarded; `test_ldap_setting`, `test_import_ldap_off` (16 tests); suite 337 OK, 1 skipped; image tests 22/22 (implementer run) (`1e785df`).
- T2 2026-11-20: `check` and `migrate` pass on an empty DB; Swagger topic list built lazily (drf-yasg renders `lazy` strings, list now current per request); `api.test_empty_database` (5 tests); `tests/run.sh` runs `check` on the empty MariaDB, no `--skip-checks`; suite 321 OK, 1 skipped; image tests 22/22 (implementer run) (`36abed0`).
- T1 2026-11-20: `manage.py test` with no labels runs the whole suite (316 tests, OK, 1 skipped = the `/find` prefix test); old `tests.py`, stubs and `app-main/test_*.py` removed; shared helpers in `publications/test_factories.py`; CLAUDE.md, validate skill, `datatransfer_script.sh` updated (`f02e5ea`).
- T0 2026-11-20: worktree and branch `agent-test-coverage` from `develop/main` (`3d69785`), `.dev.env` copied.
- 2026-11-19: decision: `publications/tests.py` and the `app-main/test_*.py` scripts are deleted; their intent is re-covered with fixture tests.

## Coverage baseline (T4, 2026-11-20)

Total: 5284 statements, 2116 missed; line 60.0 %, branch 42.8 %, combined 55.5 %.

| App / module | Line % | Branch | Combined % |
|---|---|---|---|
| publications | 58.9 | 776/1796 | 54.7 |
| api | 62.6 | 10/56 | 55.6 |
| publications_meta | 33.3 | 0/2 | 29.4 |
| find_artek | 98.3 | 16/18 | 97.1 |
| visibility, person_privacy, views_media, api/serializers | 100 | all | 100 |
| roles / permissions / media_access | 96.0 / 95.4 / 96.2 | | 94.4 / 93.4 / 92.4 |
| workflows/person.py | 80.8 | 65/92 | 78.0 |
| views.py | 70.3 | 186/352 | 66.2 |
| register_from_file.py | 33.9 | 17/92 | 29.4 |
| utils_person.py | 24.3 | 18/162 | 20.0 |
| commands generate_thumbnails / cleanup_temp_files | 0 | | 0 |

Most missed statements: views.py 339, utils_person 259, forms/mixins 187, register_from_file 144, generate_thumbnails 129, forms/person 107, utils_models 97, api/person_ajax_views 95 (0 %), commands normalize_pdf_filenames 95, cleanup_temp_files 86; then test_person_workflow (command, 84), analyze_srid_usage 82, generate_report_numbers 77 (all 0 %).

## Open questions

- Coverage target per app and per critical module: set after the T4 baseline.

## Notes for the next session

- Found in T3, for T7 (person matching): with LDAP on, `utils_person.get_from_studynumber`/`get_from_initials` call `get_or_create_person_from_ldap(person=...)`, but the parameter is `ldap_object` (TypeError on any LDAP hit; reached only via `get_person_from_string`). `register_from_file.py` study-number warning with LDAP on uses `{0}` instead of `{2}` ("add Author manually"; cosmetic).
- `USE_LDAP` for web_server: optional, default `true`; list it in the release USER_STEPS (T10).
- Dev stack from the worktree: add `-p find_artek_develop` to the compose command (the project name otherwise comes from the directory and the container names clash). A failed run left unused volumes `find_artek_agent-test-coverage_staticfiles_data`, `..._media_data` and network `find_artek_agent-test-coverage_docker_default`; remove them yourself if you like (`docker volume rm`, `docker network rm`).
- `tests/run.sh` header comment (line 55) still describes the old `tests.py`; T9 rewrites it.
- `develop/main` now has the thumbnail fix (`4f45f6d`, new label `publications.test_report_thumbnail_link` in `tests/run.sh`): merge `develop/main` into `agent-test-coverage` before T9 / before the fast-forward.
