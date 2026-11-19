# Plan: Test coverage (Phase 2)

Status: **approved 2026-11-19**. Roadmap: Phase 2; FA-R40, FA-R44, FA-R14, FA-R34, FA-R12 (the remaining part). Branch: `agent-test-coverage` (from `develop/main`), worked in its own worktree `..\find_artek_agent-test-coverage`. Starts **after `agent-confidential` is merged** (PLAN_confidential), so the smoke tests describe the final visibility rule and the two branches don't conflict in `api/views.py`, `tests/run.sh` and the test modules. Release: with the next release after that; the only behaviour changes are FA-R14 and FA-R34.

## Goal

1. `manage.py test` with no labels discovers and runs the whole suite, green, in the dev stack and in `tests/run.sh` (FA-R40). The release gate runs the full suite instead of a label list.
2. Coverage is measured (`coverage.py`, dev stack only) and meets the target set after the baseline (FA-R44); the critical paths below are covered whatever the number says.
3. Every URL has a smoke test, anonymous and logged in, and a test fails when a new URL has none.
4. `check` and `migrate` work on an empty database (FA-R14); `tests/run.sh` drops its `--skip-checks` workaround.
5. `USE_LDAP` comes from the environment, default `true` (FA-R34), with tests for on and off.
6. The PDF upload failure from the readme (FA-R12) is retested and either closed or reproduced as a test.

## Current state

- Suite layout: flat `publications/test_*.py` and `api/test_*.py` modules (Phase 1b, ~227 tests, all in the gate's `DJANGO_TEST_LABELS`, `tests/run.sh:63-69`).
- `publications/tests.py` (882 lines): `unittest` tests against specific rows of the production copy (person id 3, report 532, the media folder), imports a non-existent `utils.get_all_publications`; it breaks discovery. `publications/tests/` holds only `__pycache__` (untracked). `api/tests.py`, `publications_meta/tests.py`: empty stubs. `app-main/test_enhanced_matching.py`, `test_file_upload.py`, `test_real_names.py`: ad-hoc scripts (`django.setup()` at import) that discovery picks up.
- `api` and `publications_meta` aren't in `INSTALLED_APPS` (`settings.py:61-75`); their tests run by label/discovery anyway.
- FA-R14: `api/views.py:33-46` queries `Topic` in a decorator at class definition; `tests/run.sh:320-323,499` uses `migrate --skip-checks`.
- FA-R34: `settings.py:170` `USE_LDAP = True` hardcoded; used in `roles.py:97` and `register_from_file.py:239,270`.
- No coverage tool: `requirements-dev.in` is empty (`-c requirements.txt`).
- Not tested at all (from the PLAN_confidential survey): the read-only pages other than the report page, `/api/person/`, the report list filters (`topic`, `author_id`, `supervisor_id`, `q`, ordering), next-report-number, the person-matching workflows outside the form, `generate_thumbnails`, `cleanup_temp_files`, the Excel import parsing, the admin.
- Known suspect code to look at while testing: `Person.sorted_authorships`/`sorted_supervisorships`/`sorted_editorships` use `publication_authors` (`models.py:234-256`, the related name is `publication_author`); `thumb_file` builds the name from the PDF basename while `generate_thumbnails` uses `<number>_thumb.jpg` (`pubs_extra_tags.py:57-74`).

## Design notes

- **Old tests removed** (decided 2026-11-19): `publications/tests.py` and the three `app-main/test_*.py` scripts are deleted; what they meant to check (relations, appendices, keywords, topics, features of a report) gets fixture-based tests (T6). The "every file on disk has a DB row" check is dropped (PLAN_confidential's `check_media_access` covers the useful part).
- **Fixtures in code**, not JSON dumps of the production copy: small factory helpers in one module (`publications/test_factories.py`), reused by every test. No real names, study numbers or files from the dev database.
- **Smoke tests from the URLconf**: walk the resolved `urlpatterns`, and require an entry for every named pattern in a table `{name: (kwargs factory, expected status anonymous, as dtu_user, as artek_editor)}`. A URL without an entry fails a test, so new URLs need a smoke test.
- **Bugs found while testing**: a small, obvious fix with no behaviour decision (e.g. a wrong related name) is fixed in its own commit with the test that shows it. Anything bigger, or that changes what users see, becomes an FA-R item in the roadmap and is asked about; its test lands with the fix, not as a skipped or expected failure.
- **Coverage**: `coverage` in `requirements-dev.in` (dev stage only, not in the production image). `.coveragerc` at `app-main/`: source `publications`, `api`, `publications_meta`, `find_artek`; omit migrations and the test modules. Run: `coverage run manage.py test ... && coverage report`. The baseline (T4) is recorded in STATUS; you set the target then. The gate (`tests/run.sh`, production image) runs the suite without coverage.
- **Critical paths** (covered whatever the number): `visibility.py`, `permissions.py`, `media_access.py`, `roles.py`, `person_privacy.py`; every write view's permission check; add/edit/finalize with upload; person matching (`publications/workflows/`, `utils_person.py`); the API serializers.
- **FA-R14**: build the Swagger topic description lazily (or drop the list from it; decided in T2 by what drf-yasg allows), plus a test that runs `check` and `migrate` on an empty database.
- **FA-R34**: `USE_LDAP = env bool, default true`. Every LDAP use skips cleanly when off (login works, roles kept as `roles.py` documents, Excel import skips the directory lookup). New env variable: `.dev.env.example`, `ENVIRONMENT_SETUP.md` table, deploy-contract skill. web_server needs no change (default `true` = today); it may set it explicitly.
- **Deployment contract**: `tests/run.sh` keeps its interface (`<image>`, `--quick`, `TEST_FILTER`, last line); only what it runs changes. `USE_LDAP` is a new variable name (listed for web_server). Nothing else.

## Assumptions

- Phase 2 adds tests and fixes bugs it finds within the rule above; it doesn't refactor views (FA-R66) or upgrade Django (Phase 3).
- The smoke table's expected statuses are today's behaviour after PLAN_confidential; a status that looks wrong is a bug under the rule above, not silently encoded.
- `publications_meta` gets smoke tests for its one view and nothing else.
- CI (GitHub Actions) stays out (later option of FA-R40).
- No JS test framework; JS behaviour stays checked by hand.

## Tasks

### T0. Worktree (main session)
After `agent-confidential` is merged: `git worktree add -b agent-test-coverage ..\find_artek_agent-test-coverage develop/main`; copy `.dev.env`.

### T1. One suite, discovered (FA-R40)
- Files: delete `publications/tests.py`, `app-main/test_enhanced_matching.py`, `test_file_upload.py`, `test_real_names.py`; `api/tests.py`, `publications_meta/tests.py` (delete the stubs); new `publications/test_factories.py` (helpers moved from the 1b test modules where they repeat).
- Acceptance: `manage.py test` (no labels) runs every test module, green; the count matches the label run plus nothing missing.
- Validation: `validate`, full suite.
- Agent: implementer.
- Deployment impact: none.

### T2. Empty database (FA-R14)
- Files: `api/views.py`, `tests/run.sh` (drop `--skip-checks`, rename the test), a test for `check` + `migrate` on an empty DB.
- Acceptance: `check` and `migrate` pass on an empty MariaDB; the Swagger page still renders.
- Validation: `validate`; image tests (`tests/run.sh`).
- Agent: implementer.
- Deployment impact: none (the gate runs the same steps without the flag).

### T3. `USE_LDAP` from the environment (FA-R34)
- Files: `find_artek/settings.py`, `roles.py`, `register_from_file.py`, `.dev.env.example`, `ENVIRONMENT_SETUP.md`, `.claude/skills/deploy-contract/`, tests (`test_roles.py` and a new import test).
- Acceptance: unset → `True`; `false`/`0`/`no` → `False`; with `False` login and import work without any LDAP call.
- Validation: `validate`; image tests (settings change).
- Agent: implementer.
- Deployment impact: new variable `USE_LDAP` (optional, default `true`); listed for web_server's `webapp_find_artek.env`.

### T4. Coverage measurement (FA-R44)
- Files: `requirements-dev.in` → `python scripts/compile_lock.py` (dev lock), `app-main/.coveragerc`, `readme.md` (how to run), CLAUDE.md Commands and the `validate` skill (coverage command).
- Acceptance: coverage runs in the dev stack; baseline per app and per critical module recorded in STATUS; you set the target (open question).
- Validation: `validate`; dev image builds.
- Agent: implementer; target: you.
- Deployment impact: none (dev stage only).

### T5. URL smoke tests
- Files: new `publications/test_smoke_urls.py` (covers `api` and `publications_meta` URLs too).
- Acceptance: every named URL pattern has an entry; anonymous, `dtu_user` and `artek_editor` statuses asserted; a missing entry fails.
- Validation: `validate`; full suite.
- Agent: implementer.
- Deployment impact: none.

### T6. Models, relations, API lists
- Files: new `publications/test_models.py`, `api/test_report_list.py`, `api/test_person_api.py`.
- Acceptance: the relations the old `tests.py` meant to check (authors, supervisors, editors and their order; appendices; keywords; topics; features of a report) on fixtures; report list filters `topic`, `author_id`, `supervisor_id`, `q` (title, abstract, keyword), ordering; `/api/person/` fields; next-report-number. Bugs per the design notes.
- Validation: `validate`; full suite.
- Agent: implementer.
- Deployment impact: none.

### T7. Workflows, commands, import
- Files: tests for `publications/workflows/` and `utils_person.py` outside the form, `generate_thumbnails` and `cleanup_temp_files` (on a tmp `MEDIA_ROOT`, a generated one-page PDF), Excel import parsing (an `.xlsx` built in the test with `openpyxl`, `USE_LDAP=False`).
- Acceptance: critical paths covered; coverage meets the target from T4, or STATUS lists what is missing and why.
- Validation: `validate`; full suite with coverage.
- Agent: implementer.
- Deployment impact: none.

### T8. PDF upload in production (FA-R12, you)
Upload a large PDF (~50 MB) through the edit form on production with a test report, after 2026.3 is deployed. If it fails, note the size, the error page and the time; the main session then checks Django's upload settings and web_server's nginx `client_max_body_size` / timeouts and writes a test for the Django part.

### T9. Gate runs the full suite
- Files: `tests/run.sh` (no `DJANGO_TEST_LABELS` list: the full discovered suite), its header comment, readme.
- Acceptance: `bash tests/run.sh find_artek:local` passes and runs the same number of Django tests as `manage.py test` in the dev stack.
- Validation: image tests.
- Agent: implementer.
- Deployment impact: `build_image.sh` runs longer; interface unchanged.

### T10. Release (you)
With the next release after T9: steps in `docs/plan/USER_STEPS_<release>.md`; mention `USE_LDAP` to web_server (optional).

## Out of scope

- CI on GitHub Actions; ruff/mypy (FA-R40 later options).
- JS tests.
- Person-disambiguation refactor (FA-R66), Django upgrade (Phase 3).
- Fixing bugs that need a behaviour decision: they become roadmap items.
