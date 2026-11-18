# Status: Registration (Phase 1b)

Plan: [PLAN_registration.md](PLAN_registration.md). Branch: `agent-registration` (from `develop/main` at `58286e0`), worktree `..\find_artek_agent-registration`.

## Now

**Blocked on Docker Desktop (2026-11-18):** new containers hung in "Created" (running ones were fine) after three parallel image builds + `tests/run.sh` runs under memory pressure; Docker Desktop didn't come back after a quit, owner is rebooting the PC. Code for T1, T3, T6 is written, **uncommitted, in their worktrees** (files on disk, survive the reboot); **none validated yet** (no check, makemigrations, migrate or Django test has run).

Resume after the reboot (main session):
1. `docker ps -a`: Docker works (`docker run --rm --network none --entrypoint /bin/true find_artek:registration` returns at once); remove leftover "Created" containers from the old runs (`fa-test-*`, random names like `thirsty_mirzakhani`): `docker ps -a --filter status=created`, then `docker rm` those. The dev stack `webapp-find-artek-dev` etc. must be up (restart policy), else `$DC up -d` from `find_artek_DEVELOP` (no `--build` needed, no `-v`).
2. Check the worktrees: `git -C ..\find_artek_agent-registration status`, same for `-t3`, `-t6` (expected files: below).
3. Run the gates **one at a time** (not in parallel: memory), in Git Bash, each in its worktree: `docker build -t find_artek:<tag> . && bash tests/run.sh find_artek:<tag>` with tags `registration` (T1), `registration-t3`, `registration-t6` (T6 must be rebuilt: its image predates `CAS_REDIRECT_URL`).
4. Review each diff (`git diff --ignore-cr-at-eol`), fix failures (implementer with the failure output), commit on its branch as `T1: …`, `T3: …`, `T6: …`; cherry-pick the T3 and T6 commits onto `agent-registration` (conflict expected only in `DJANGO_TEST_LABELS` in `tests/run.sh`: keep all labels); run `tests/run.sh` once more on `agent-registration`; remove the `-t3`/`-t6` worktrees and branches.
5. Then T2 (you) and T4/T5 (after T3; one at a time or in separate worktrees, but gates sequential).

Expected uncommitted files:
- `..\find_artek_agent-registration` (T1): new `app-main/publications/migrations/0003_registration_groups.py`, `app-main/publications/roles.py`, `app-main/publications/test_roles.py`; modified `app-main/publications/apps.py`, `app-main/find_artek/settings.py`, `.dev.env.example`, `ENVIRONMENT_SETUP.md`, `tests/run.sh`.
- `..\find_artek_agent-registration-t3` (T3): modified `app-main/publications/models.py`, `tests/run.sh`; new `app-main/publications/test_permissions_models.py`.
- `..\find_artek_agent-registration-t6` (T6): modified `app-main/find_artek/settings.py`, `app-main/templates/admin/login.html`, `app-main/publications/test_upload_appendix_access.py`, `tests/run.sh`; new `app-main/publications/test_login_redirect.py`.

Parallel worktrees (temporary, from `agent-registration` at `58286e0`): `..\find_artek_agent-registration-t3` (`agent-registration-t3`), `..\find_artek_agent-registration-t6` (`agent-registration-t6`).

## Done

- 2026-11-18: plan written and approved. Decisions: 1b before FA-R66 with the new-person bug reproduced first (T8); keep the session-based form flow; Excel import / change number / bulk delete for `artek_editor` only; new keywords by anyone who may edit the report (topics list-only); `artek_staff`/`artek_editor` **only** from the AD lists (no hand assignment; empty setting = nobody); abandoned temp uploads deferred (FA-R70, low priority).
- T0 2026-11-18: worktree `..\find_artek_agent-registration` on `agent-registration`.

## Open questions

- AD groups requested from IT (2026-11-18): their DNs go into `LDAP_GROUP_ARTEK_STAFF` / `LDAP_GROUP_ARTEK_EDITOR`. Until then only superusers can add reports. Decide at T11 whether 2026.3 waits for them.

## Notes for the next session

- T1 (written, not run): migration `0003_registration_groups` (deps publications 0002, auth 0012, contenttypes 0002) calls `create_permissions` with the real app config and historical `apps`, `get_or_create` per group, missing codename → `RuntimeError`, reverse deletes the three groups. `roles.py`: `ad_group_memberships(username, group_dns)` (ldap3, 5 s timeouts, filter `(&(sAMAccountName=…)(memberOf:1.2.840.113556.1.4.1941:=…))`, raises `LdapLookupError` without secrets), `update_user_roles(user)`, handler on `django_cas_ng.signals.cas_user_authenticated` (django-cas-ng 5.0.1) connected in `apps.py` with `dispatch_uid`. 16 tests in `test_roles.py`; the reversibility test (MigrationExecutor 0003→0002→0003 inside a `TestCase`) may be brittle on MariaDB: if so, `TransactionTestCase` or drop it (say so). Checked 2026-11-18: the dev DB (copy of production) has **no** auth groups, so `get_or_create` creates fresh groups and changes no existing rows. Open in review: the `publications.roles` logger has no handler in `LOGGING` (warnings go to stderr = container log, not `debug.log`); a partially filled setting removes the empty one's role even if the lookup fails (follows "empty = nobody").
- T3 (written, not run): helpers `Publication.is_own_publication_of`, `Feature.is_created_by` (created_by only, not modified_by); `sorted_supervisors`/`sorted_editors` field names fixed; `has_model_permission` callers pass `model_name`; 27 tests in `test_permissions_models.py`. Found, out of scope: `Person.sorted_authorships/_supervisorships/_editorships` (`models.py` ~220-240) use plural related names that don't exist (latent AttributeError) → roadmap at plan end.
- T6 (written, not run): `LOGIN_URL = 'cas_ng_login'`; also `CAS_REDIRECT_URL = 'publications:frontpage'` (default `/` sent login/logout without next outside `/find/`); `templates/admin/login.html` uses `{% url 'admin-cas-login' %}`. The image built before the `CAS_REDIRECT_URL` change: rebuild. django-cas-ng 5.0.1 builds the service URL from `request.path`, so it keeps `/find/`; the `https` depends on nginx sending `X-Forwarded-Proto` (web_server, not verified). Prefix bugs listed, not fixed: `reports_snippets/report_td.html:3` (`/publications/report/...` hard-coded), `shared_snippets/supervisorlist_short.html:3,20,24,36` (old `/pubs/person/...`) → roadmap at plan end (or T9 if cheap).

- Survey of the write views and their guards is in the plan's "Current state" (line numbers as of `b2cc908`).
- `publications/tests.py` is not a usable test module; new tests go in `publications/test_*.py` modules, style as `test_upload_appendix_access.py`.
- Validation for the worktree: the dev stack runs from `find_artek_DEVELOP` (not the branch). Each task adds its test modules to `DJANGO_TEST_LABELS` in `tests/run.sh` and validates with `docker build -t find_artek:registration . && bash tests/run.sh find_artek:registration` in the worktree (covers check, `check --deploy`, makemigrations --check, migrate on an empty MariaDB, the Django labels).
