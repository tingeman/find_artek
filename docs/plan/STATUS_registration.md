# Status: Registration (Phase 1b)

Plan: [PLAN_registration.md](PLAN_registration.md). Branch: `agent-registration` (from `develop/main` at `58286e0`), worktree `..\find_artek_agent-registration`.

## Now

**Blocked on Docker Desktop (2026-11-18):** new containers hang in "Created" (running ones are fine), so `tests/run.sh` can't run. Owner to restart Docker Desktop. Code for T1, T3, T6 is written, uncommitted, in their worktrees; none validated yet. After the restart: remove the stuck `fa-test-*` / random-named "Created" containers, rebuild and run `tests/run.sh` in each worktree, review, commit T1 → T3 → T6 on `agent-registration` (cherry-pick from `agent-registration-t3` / `-t6`, resolve the `DJANGO_TEST_LABELS` line), remove the `-t3`/`-t6` worktrees and branches. Then T2 (you) and T4.

Parallel worktrees (temporary, from `agent-registration` at `58286e0`): `..\find_artek_agent-registration-t3` (`agent-registration-t3`), `..\find_artek_agent-registration-t6` (`agent-registration-t6`).

## Done

- 2026-11-18: plan written and approved. Decisions: 1b before FA-R66 with the new-person bug reproduced first (T8); keep the session-based form flow; Excel import / change number / bulk delete for `artek_editor` only; new keywords by anyone who may edit the report (topics list-only); `artek_staff`/`artek_editor` **only** from the AD lists (no hand assignment; empty setting = nobody); abandoned temp uploads deferred (FA-R70, low priority).
- T0 2026-11-18: worktree `..\find_artek_agent-registration` on `agent-registration`.

## Open questions

- AD groups requested from IT (2026-11-18): their DNs go into `LDAP_GROUP_ARTEK_STAFF` / `LDAP_GROUP_ARTEK_EDITOR`. Until then only superusers can add reports. Decide at T11 whether 2026.3 waits for them.

## Notes for the next session

- T3 (written, not run): helpers `Publication.is_own_publication_of`, `Feature.is_created_by` (created_by only, not modified_by); `sorted_supervisors`/`sorted_editors` field names fixed; `has_model_permission` callers pass `model_name`; 27 tests in `test_permissions_models.py`. Found, out of scope: `Person.sorted_authorships/_supervisorships/_editorships` (`models.py` ~220-240) use plural related names that don't exist (latent AttributeError) → roadmap at plan end.
- T6 (written, not run): `LOGIN_URL = 'cas_ng_login'`; also `CAS_REDIRECT_URL = 'publications:frontpage'` (default `/` sent login/logout without next outside `/find/`); `templates/admin/login.html` uses `{% url 'admin-cas-login' %}`. The image built before the `CAS_REDIRECT_URL` change: rebuild. django-cas-ng 5.0.1 builds the service URL from `request.path`, so it keeps `/find/`; the `https` depends on nginx sending `X-Forwarded-Proto` (web_server, not verified). Prefix bugs listed, not fixed: `reports_snippets/report_td.html:3` (`/publications/report/...` hard-coded), `shared_snippets/supervisorlist_short.html:3,20,24,36` (old `/pubs/person/...`) → roadmap at plan end (or T9 if cheap).

- Survey of the write views and their guards is in the plan's "Current state" (line numbers as of `b2cc908`).
- `publications/tests.py` is not a usable test module; new tests go in `publications/test_*.py` modules, style as `test_upload_appendix_access.py`.
- Validation for the worktree: the dev stack runs from `find_artek_DEVELOP` (not the branch). Each task adds its test modules to `DJANGO_TEST_LABELS` in `tests/run.sh` and validates with `docker build -t find_artek:registration . && bash tests/run.sh find_artek:registration` in the worktree (covers check, `check --deploy`, makemigrations --check, migrate on an empty MariaDB, the Django labels).
