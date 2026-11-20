# Status: Test coverage (Phase 2)

Plan: [PLAN_test-coverage_COMPLETE.md](PLAN_test-coverage_COMPLETE.md). Branch: `agent-test-coverage` (from `develop/main`), worktree `..\find_artek_agent-test-coverage`.

## Now

Plan finished 2026-11-20 (release `2026.5` deployed and checked). Archived; deferred items in the roadmap (FA-R88 to FA-R92, additions to FA-R57, FA-R70).

## Done

- T10, T8 2026-11-20: 2026.5 deployed (you), server and browser checks pass. 100 MB PDF refused by the form's 50 MB limit (FA-R88); deleted report still in the cached list (FA-R89).
- T10 (part) 2026-11-20: `develop/main` fast-forwarded to `60bec29`, tag `2026.5` (local), bundle built and tested (22/22, Django 538 OK), on the releases share, web_server `releases.yml` committed (`6b0304d`).
- T9 follow-up 2026-11-20: suite 60 s -> 23 s (dev), gate 2m11 -> 1m32: test users without password (212 PBKDF2 hashes of ~0.16 s; all tests use `force_login`), `--buffer`, debug `print` in `BaseView` removed. `--parallel` rejected: needs `mysqldump` in the production image (gate checks no admin tools). Dev 538 OK, 1 skipped; image tests 22/22 (`a3ac558`).
- T9 2026-11-20: `tests/run.sh` runs the whole discovered suite (no `DJANGO_TEST_LABELS`), production settings; docs and skills updated; three `test_import_excel` upload-page tests fixed for the `/find` prefix (followed the prefixed redirect as a path, 404) and `test_report_thumbnail_link` import fixed after the merge (`8b1e4fd`); failure summary shows FAIL/ERROR lines only. Dev 538 OK, 1 skipped; image tests 22/22, Django 538 OK; full gate ~6 min (`b21c38f`).
- T7b 2026-11-20: Excel import checked and all or nothing (one transaction, problems listed by sheet and row), existing numbers skipped, column aliases, title may be empty, editors optional, existing topics only, keywords imported, year rule 90-99 = 19YY; new template `static/publications/docs/ARTEK_report_list.xlsx` with a Help sheet (the page link was broken: file missing, `{{STATIC_URL}}` empty) (`e549ecd`). Suite 536 OK, 1 skipped; coverage 71.0 % (register_from_file 97.3).
- T7 follow-ups 2026-11-20: directory-entry person match fixed (empty initials/id_number no longer match; an entry without identifiers no longer matches every person; an exact match is preferred) (`f73c34e`); `cleanup_temp_files` never deletes DB rows, the crashing temp-publication part removed (`c5ed19f`). Suite 509 OK, 1 skipped; coverage 70.0 %.
- T7 2026-11-20: `test_utils_person`, `test_workflow_person`, `test_management_commands`, `test_import_excel` (93 tests). Bugs fixed: LDAP lookups passed `person=` (TypeError), `get_from_namestring` NameError on every plain name, an empty topic cell stopped the Excel import, LDAP warning text (`1c0e529`). Before it, `PersonSelectView` removed (`43a0514`). Suite 498 OK, 1 skipped; coverage 69.7 % (utils_person 68.7, register_from_file 76.8, workflows/person 95.5, generate_thumbnails 81.5, cleanup_temp_files 72.7).
- 2026-11-20 (decided with you): `PersonSelectView` (`/select/persons/`) is removed with its template and unused forms. It is a predecessor of the person workflow (`workflows/person.py`, `PersonWorkflowMixin`), and it reads session keys that nothing writes, so its POST gives 500.
- 2026-11-20 (decided with you): non-numeric `author_id`/`supervisor_id` on `/api/report/` gives 400 instead of 500 (`3fac0b7`); suite 407 OK, 1 skipped.
- T6 2026-11-20: `publications/test_models.py`, `api/test_report_list.py`, `api/test_person_api.py`, `api/test_next_report_number.py` (64 tests); factories `make_person`, `make_report(supervisors=, editors=, topics=, keywords=)`; bug fixed: `Person.sorted_authorships/supervisorships/editorships` used non-existent related names (AttributeError; unused, no visible change) (`24838dd`, `5bfe2ad`); suite 406 OK, 1 skipped; coverage 58.5 % (views.py 73.3, models.py 85.7, api/views.py 98.1).
- T5 2026-11-20: `publications/test_smoke_urls.py`: 48 named URLs (+ root redirect) for anonymous, `dtu_user`, `artek_editor`; missing entry fails (checked); admin internals via `admin:index`; suite 342 OK, 1 skipped; coverage 56.6 % (views.py 70.2 %) (`e0286cc`). Before it, decided with you: dead `check_person_ajax` (500 on every call), its unused template and the unrouted `api/person_ajax_views.py` removed (`56c7d1e`).
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


## Notes for the next session

- T7b: a row that fails the first check (type, topic, authors, number/year) isn't saved even temporarily, so its person problems show only on the next upload. Functional check after the release: the template link on the `/find/` upload page downloads the file. Release notes for editors: the import is now all or nothing; existing numbers are skipped instead of renumbered.

- For the roadmap at Finish (decided 2026-11-20, from T7):
  - New FA-R item (FA-R41 style), dead code: `utils_person.get_person_from_string`, `get_from_*`, `get_from_namestring`, `add_persons_to_publication` (broken), `choose_person`; only tests call them. Also the four remaining commented `AddEditReportView` lines in `urls.py`.
  - FA-R70 addition: `cleanup_temp_files` leaves the `FileObject` row of a deleted temp file, and it deletes an upload older than max-age even while that form is still open.
  - Live data check (roadmap): imports with LDAP on may have linked wrong persons (the `get_or_create_person_from_ldap` bug); not checked.
  - Import cycle `workflows/person.py` <-> `forms/mixins.py` (works only when forms load first).

- Found in T6, for T7: command `generate_report_numbers` imports `publications.utils` (doesn't exist; functions are in `utils_models`): broken. `utils_models.generate_next_report_number(exclude_ids=...)` has no effect (filters an unused set); no caller passes it. `utils_models.py` 178-316 (batch numbering, format checks) uncovered.
- Roadmap candidate (refactor, not a fix): `Person.sorted_*` use `.extra(CAST(year AS INTEGER))` though `year` is an IntegerField.
- Found in T5, for T7 (workflows): `PersonSelectView` (`select-persons`) `get_session_config` reverses `publications:publication_final_save` and `publications:edit_report_final_save`, which no longer exist: its POST likely raises NoReverseMatch. Check whether the view is reachable from the UI (`ReportFormView.select_persons_url`); test or remove (ask).
- Found in T5: management command `test_person_workflow` imports `publications.person_workflow`, which doesn't exist (dead command); candidate for FA-R41 leftovers.
- Found in T5, roadmap candidate: `publications_meta/views.py` hard-codes the two usernames allowed into the admin via `admin-cas-login` (access rule; out of scope here).

- Decided 2026-11-20: no numeric coverage target. Critical paths covered, beyond that what makes sense; tests check behaviour, not implementation; the report is a map for finding untested behaviour. One-off maintenance commands (normalize_pdf_filenames, analyze_srid_usage, generate_report_numbers, test_person_workflow) stay in the report, no tests in this plan.

- Found in T3, for T7 (person matching): with LDAP on, `utils_person.get_from_studynumber`/`get_from_initials` call `get_or_create_person_from_ldap(person=...)`, but the parameter is `ldap_object` (TypeError on any LDAP hit; reached only via `get_person_from_string`). `register_from_file.py` study-number warning with LDAP on uses `{0}` instead of `{2}` ("add Author manually"; cosmetic).
- `USE_LDAP` for web_server: optional, default `true`; list it in the release USER_STEPS (T10).
- Dev stack from the worktree: add `-p find_artek_develop` to the compose command (the project name otherwise comes from the directory and the container names clash). A failed run left unused volumes `find_artek_agent-test-coverage_staticfiles_data`, `..._media_data` and network `find_artek_agent-test-coverage_docker_default`; remove them yourself if you like (`docker volume rm`, `docker network rm`).
- For T10 USER_STEPS: `build_image.sh` now takes ~1.5 min (whole Django suite); interface unchanged.
- Roadmap candidate (FA-R41 style): `api/views.py:25,29` logs `WARNING views.py is loaded` at import (debug leftover, shows in every test run and in production logs).
