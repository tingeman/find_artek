# Status: Registration (Phase 1b)

Plan: [PLAN_registration.md](PLAN_registration.md). Branch: `agent-registration` (from `develop/main` at `58286e0`), worktree `..\find_artek_agent-registration`.

## Now

T1, T3, T6 committed on `agent-registration` (`c75d19c`, `f4ce8b4`, `793fdd5`); combined gate on the branch: 21/21 checks, 62 Django tests (2026-11-18). Temporary `-t3`/`-t6` worktrees and branches removed.

Next:
- **T2 (you):** CAS username check in the dev stack running the branch code (steps below).
- **T4 (implementer)** in worktree `..\find_artek_agent-registration-t4` (branch `agent-registration-t4` from `agent-registration`), so the T2 dev stack built from `..\find_artek_agent-registration` is not disturbed; cherry-pick onto `agent-registration` when done. T5 after T4 (both touch `views.py`).

T2 steps (Git Bash): copy `.dev.env` yourself from `find_artek_DEVELOP` into `..\find_artek_agent-registration` (ignored by `*.env`), then in that worktree:
```bash
DC="docker compose -p find_artek_develop -f docker-compose.yml -f docker-compose.develop.yml"
$DC up -d --build
$DC exec -T webapp-find-artek python manage.py migrate --settings find_artek.development_settings   # applies publications 0003: adds the 3 groups, changes no existing row
```
Log in at `http://localhost:8098/login`, then run the shell command from the plan's T2. Back to develop/main afterwards: in `find_artek_DEVELOP`, `docker compose -f docker-compose.yml -f docker-compose.develop.yml up -d --build` (0003 stays applied in the dev DB; harmless, the groups stay).

## Done

- 2026-11-18: plan written and approved. Decisions: 1b before FA-R66 with the new-person bug reproduced first (T8); keep the session-based form flow; Excel import / change number / bulk delete for `artek_editor` only; new keywords by anyone who may edit the report (topics list-only); `artek_staff`/`artek_editor` **only** from the AD lists (no hand assignment; empty setting = nobody); abandoned temp uploads deferred (FA-R70, low priority).
- T0 2026-11-18: worktree `..\find_artek_agent-registration` on `agent-registration`.
- T1 2026-11-18: groups `dtu_user`/`artek_staff`/`artek_editor` (migration 0003), roles from AD lists at every CAS login; 16 tests (`c75d19c`)
- T3 2026-11-18: model permission methods fixed (model_name codenames, related names, own helpers, anonymous never matches); 27 tests (`f4ce8b4`)
- T6 2026-11-18: `LOGIN_URL`/`CAS_REDIRECT_URL` as URL names, admin CAS link reversed; existing `assertRedirectsToLogin` in `test_upload_appendix_access.py` adapted to the URL name (`793fdd5`)

## Open questions

- AD groups requested from IT (2026-11-18): their DNs go into `LDAP_GROUP_ARTEK_STAFF` / `LDAP_GROUP_ARTEK_EDITOR`. Until then only superusers can add reports. Decide at T11 whether 2026.3 waits for them.

## Notes for the next session

- T1 (validated 2026-11-18; the reversibility test passes on MariaDB): migration `0003_registration_groups` (deps publications 0002, auth 0012, contenttypes 0002) calls `create_permissions` with the real app config and historical `apps`, `get_or_create` per group, missing codename → `RuntimeError`, reverse deletes the three groups. `roles.py`: `ad_group_memberships(username, group_dns)` (ldap3, 5 s timeouts, filter `(&(sAMAccountName=…)(memberOf:1.2.840.113556.1.4.1941:=…))`, raises `LdapLookupError` without secrets), `update_user_roles(user)`, handler on `django_cas_ng.signals.cas_user_authenticated` (django-cas-ng 5.0.1) connected in `apps.py` with `dispatch_uid`. 16 tests in `test_roles.py`; the reversibility test (MigrationExecutor 0003→0002→0003 inside a `TestCase`) may be brittle on MariaDB: if so, `TransactionTestCase` or drop it (say so). Checked 2026-11-18: the dev DB (copy of production) has **no** auth groups, so `get_or_create` creates fresh groups and changes no existing rows. Open in review: the `publications.roles` logger has no handler in `LOGGING` (warnings go to stderr = container log, not `debug.log`); a partially filled setting removes the empty one's role even if the lookup fails (follows "empty = nobody").
- T3 (validated 2026-11-18): helpers `Publication.is_own_publication_of`, `Feature.is_created_by` (created_by only, not modified_by); `sorted_supervisors`/`sorted_editors` field names fixed; `has_model_permission` callers pass `model_name`; 27 tests in `test_permissions_models.py`. Found, out of scope: `Person.sorted_authorships/_supervisorships/_editorships` (`models.py` ~220-240) use plural related names that don't exist (latent AttributeError) → roadmap at plan end.
- T6 (validated 2026-11-18): `LOGIN_URL = 'cas_ng_login'`; also `CAS_REDIRECT_URL = 'publications:frontpage'` (default `/` sent login/logout without next outside `/find/`); `templates/admin/login.html` uses `{% url 'admin-cas-login' %}`. django-cas-ng 5.0.1 builds the service URL from `request.path`, so it keeps `/find/`; the `https` depends on nginx sending `X-Forwarded-Proto` (web_server, not verified). Prefix bugs listed, not fixed: `reports_snippets/report_td.html:3` (`/publications/report/...` hard-coded), `shared_snippets/supervisorlist_short.html:3,20,24,36` (old `/pubs/person/...`) → roadmap at plan end (or T9 if cheap).

- Survey of the write views and their guards is in the plan's "Current state" (line numbers as of `b2cc908`).
- `publications/tests.py` is not a usable test module; new tests go in `publications/test_*.py` modules, style as `test_upload_appendix_access.py`.
- Validation for the worktree: the dev stack runs from `find_artek_DEVELOP` (not the branch). Each task adds its test modules to `DJANGO_TEST_LABELS` in `tests/run.sh` and validates with `docker build -t find_artek:registration . && bash tests/run.sh find_artek:registration` in the worktree (covers check, `check --deploy`, makemigrations --check, migrate on an empty MariaDB, the Django labels).
