# Status: Registration (Phase 1b)

Plan: [PLAN_registration.md](PLAN_registration.md). Branch: `agent-registration` (from `develop/main` at `58286e0`), worktree `..\find_artek_agent-registration`.

## Now

T1, T3, T6 on `agent-registration` (`c75d19c`, `f4ce8b4`, `793fdd5`). T4 committed on `agent-registration-t4` (`0f41c54`, worktree `..\find_artek_agent-registration-t4`), gate 21/21, 96 Django tests; **not yet fast-forwarded** onto `agent-registration`: waits until T2 is done, so the worktree the dev stack is built from doesn't change mid-build. Then: `git -C ..\find_artek_agent-registration merge --ff-only agent-registration-t4`, remove the `-t4` worktree, branch and image.

Next:
- **T2 (you), in progress:** `.dev.env` is copied into `..\find_artek_agent-registration`. In PowerShell:
  ```powershell
  cd C:\thin\02_Code\docker_projects\find_artek_agent-registration
  $DC = @('compose','-p','find_artek_develop','-f','docker-compose.yml','-f','docker-compose.develop.yml')
  docker @DC up -d --build
  docker @DC exec -T webapp-find-artek python manage.py migrate --settings find_artek.development_settings   # applies publications 0003: adds the 3 groups, changes no existing row
  # log in at http://localhost:8098/login, then:
  docker @DC exec -T webapp-find-artek python manage.py shell --settings find_artek.development_settings -c 'from django.contrib.auth.models import User; u=User.objects.order_by("-last_login").first(); print(u.username, list(u.groups.values_list("name", flat=True)))'
  ```
  Back to develop/main afterwards: `cd C:\thin\02_Code\docker_projects\find_artek_DEVELOP; docker compose -f docker-compose.yml -f docker-compose.develop.yml up -d --build` (0003 stays applied in the dev DB; harmless).
- **T5 (implementer)** after the T4 fast-forward (both touch `views.py`); T4 adds the mixin in `publications/permissions.py`, T5 needs the `manage` action and a decorator for function views (not added in T4).

## Done

- 2026-11-18: plan written and approved. Decisions: 1b before FA-R66 with the new-person bug reproduced first (T8); keep the session-based form flow; Excel import / change number / bulk delete for `artek_editor` only; new keywords by anyone who may edit the report (topics list-only); `artek_staff`/`artek_editor` **only** from the AD lists (no hand assignment; empty setting = nobody); abandoned temp uploads deferred (FA-R70, low priority).
- T0 2026-11-18: worktree `..\find_artek_agent-registration` on `agent-registration`.
- T1 2026-11-18: groups `dtu_user`/`artek_staff`/`artek_editor` (migration 0003), roles from AD lists at every CAS login; 16 tests (`c75d19c`)
- T3 2026-11-18: model permission methods fixed (model_name codenames, related names, own helpers, anonymous never matches); 27 tests (`f4ce8b4`)
- T6 2026-11-18: `LOGIN_URL`/`CAS_REDIRECT_URL` as URL names, admin CAS link reversed; existing `assertRedirectsToLogin` in `test_upload_appendix_access.py` adapted to the URL name (`793fdd5`)
- T4 2026-11-18: `publications/permissions.py` (`user_may`, `PublicationPermissionMixin`: 405 for a refused method, then 302 to login, 404, 403), on add/edit/review/finalize, verify/unverify (POST only), delete (creator-not-listed no longer may delete), appendix upload; review `post()` 307 to finalize, finalize GET redirects to review; 34 tests in `test_report_access.py` (`0f41c54`, on `agent-registration-t4`)

## Open questions

- AD groups requested from IT (2026-11-18): their DNs go into `LDAP_GROUP_ARTEK_STAFF` / `LDAP_GROUP_ARTEK_EDITOR`. Until then only superusers can add reports. Decide at T11 whether 2026.3 waits for them.

## Notes for the next session

- T1 (validated 2026-11-18; the reversibility test passes on MariaDB): migration `0003_registration_groups` (deps publications 0002, auth 0012, contenttypes 0002) calls `create_permissions` with the real app config and historical `apps`, `get_or_create` per group, missing codename → `RuntimeError`, reverse deletes the three groups. `roles.py`: `ad_group_memberships(username, group_dns)` (ldap3, 5 s timeouts, filter `(&(sAMAccountName=…)(memberOf:1.2.840.113556.1.4.1941:=…))`, raises `LdapLookupError` without secrets), `update_user_roles(user)`, handler on `django_cas_ng.signals.cas_user_authenticated` (django-cas-ng 5.0.1) connected in `apps.py` with `dispatch_uid`. 16 tests in `test_roles.py`; the reversibility test (MigrationExecutor 0003→0002→0003 inside a `TestCase`) may be brittle on MariaDB: if so, `TransactionTestCase` or drop it (say so). Checked 2026-11-18: the dev DB (copy of production) has **no** auth groups, so `get_or_create` creates fresh groups and changes no existing rows. Open in review: the `publications.roles` logger has no handler in `LOGGING` (warnings go to stderr = container log, not `debug.log`); a partially filled setting removes the empty one's role even if the lookup fails (follows "empty = nobody").
- T3 (validated 2026-11-18): helpers `Publication.is_own_publication_of`, `Feature.is_created_by` (created_by only, not modified_by); `sorted_supervisors`/`sorted_editors` field names fixed; `has_model_permission` callers pass `model_name`; 27 tests in `test_permissions_models.py`. Found, out of scope: `Person.sorted_authorships/_supervisorships/_editorships` (`models.py` ~220-240) use plural related names that don't exist (latent AttributeError) → roadmap at plan end.
- T6 (validated 2026-11-18): `LOGIN_URL = 'cas_ng_login'`; also `CAS_REDIRECT_URL = 'publications:frontpage'` (default `/` sent login/logout without next outside `/find/`); `templates/admin/login.html` uses `{% url 'admin-cas-login' %}`. django-cas-ng 5.0.1 builds the service URL from `request.path`, so it keeps `/find/`; the `https` depends on nginx sending `X-Forwarded-Proto` (web_server, not verified). Prefix bugs listed, not fixed: `reports_snippets/report_td.html:3` (`/publications/report/...` hard-coded), `shared_snippets/supervisorlist_short.html:3,20,24,36` (old `/pubs/person/...`) → roadmap at plan end (or T9 if cheap).

- T4 found, out of scope (T5/T7/roadmap): `ChangeReportNumberView` still login-only (only the pencil is hidden); add-feature buttons in `report.html` keyed on `can_edit_publication`; add and edit share the session key `form_data` and edit-finalize doesn't compare it with `session['publication_id']` (data entered for another report could be saved onto one the user may edit; T7); debug prints left in `ReportReviewView.get`, finalize, `_handle_relationships`, `ReportView` (T5); `ReportView` answers an unverified report for anonymous users with 200 + access-denied template instead of 403; `report.old.html` has GET verify links (FA-R41 leftover, not rendered); duplicate import of `disambiguate_person_step`/`complete_person_workflow` in `views.py`.
- Survey of the write views and their guards is in the plan's "Current state" (line numbers as of `b2cc908`).
- `publications/tests.py` is not a usable test module; new tests go in `publications/test_*.py` modules, style as `test_upload_appendix_access.py`.
- Validation for the worktree: the dev stack runs from `find_artek_DEVELOP` (not the branch). Each task adds its test modules to `DJANGO_TEST_LABELS` in `tests/run.sh` and validates with `docker build -t find_artek:registration . && bash tests/run.sh find_artek:registration` in the worktree (covers check, `check --deploy`, makemigrations --check, migrate on an empty MariaDB, the Django labels).
