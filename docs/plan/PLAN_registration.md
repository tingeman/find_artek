# Plan: Registration (Phase 1b)

Status: **approved 2026-11-18; T12-T16 added 2026-11-18 (user data, GDPR, features); T12 reduced to name/e-mail the same day**. Roadmap: Phase 1b; FA-R54, FA-R53, FA-R55 (with FA-R12), FA-R56, FA-R67, FA-R68. Branch: `agent-registration` (from `develop/main`), worked in its own worktree `..\find_artek_agent-registration`, so this checkout stays untouched. Release: `2026.3`.

## Goal

1. Roles as decided for FA-R54: three Django groups (`dtu_user`, `artek_staff`, `artek_editor`) created by a data migration; every CAS login gets `dtu_user`; `artek_staff` and `artek_editor` come **only** from membership of the two AD groups requested from IT (decided 2026-11-18, replaces "by hand until then"), synchronised at every login.
2. Every write view checks login **and** the matching permission, in one place (FA-R53). Anonymous and plain DTU users can no longer add, edit, renumber, import or verify reports they have no right to. Nothing becomes visible to anonymous users that is hidden today.
3. The add/edit report form works end to end, with tests: PDF upload, new keywords, no orphaned temp files, a review step that can't be skipped around the permission check (FA-R55). The new-person bug (FA-R12) is reproduced as a test and either fixed here or handed to FA-R66.
4. Permitted users reach registration from a menu (FA-R56).
5. The login redirect stays under `/find/` (FA-R67); appendix uploads record the user (FA-R68).
6. Personal data (added 2026-11-18): name and e-mail of a logged-in user come from AD at every login; study numbers and student e-mails are hidden from anonymous visitors; phone and address fields are no longer shown or edited; a document describes how the app handles user data and permissions (T12-T14).
7. The new tests are in `tests/run.sh`, and release `2026.3` is built, deployed and checked by you.

## Current state

Survey 2026-11-18 (paths under `app-main/`):

- **Write views** (`publications/views.py`, URL names in `publications/urls.py`):

  | View | Guard today |
  |---|---|
  | `ReportFormView` 316 (`add_report`, `edit_report`) | login only, no edit check |
  | `ReportReviewView` 466 | **none**; edit mode only sets `context['error']` (501); `post()` 762 redirects to URL names that don't exist (`edit_finalize`, `add_finalize`) |
  | `ReportFinalizeView` 774 | login only, saves without any check (feature_gap S2) |
  | `VerifyReportView` / `UnverifyReportView` 1111/1143 | login + `is_verifiable_by`, but the change happens on **GET** |
  | `ChangeReportNumberView` 1862 | login only (renames files) |
  | `AddFeatureCoordinatesView` 1934, `AddFeatureByMapView` 2053 | login only |
  | `DeleteReportView` 2162 | login + superuser / `created_by` / `delete_publication` (2186, 2201) |
  | `DeleteFeatureView` 2277 | `delete_feature` or `delete_own_feature`, ownership never checked |
  | `check_person_ajax` 2391, `add_person_ajax` 2478 | login only (the second creates a Person) |
  | `AddReportsFromFileUploadView` 2511 | login only; file stays in `MEDIA_ROOT/uploads` (S5) |
  | `BulkDeletePublicationsView` 2542 | login + `delete_publication` |
  | `UploadAppendixView` 1676 | login + `is_editable_by` (FA-R52) |
  | `PersonSelectView` 1176, `workflows/person.py` 270/368 | login (session only) |

- **Debug leftovers:** `find_artek/urls.py:28-37,88` `DebugRootView` at `debug-root/`, public. `views.py` has 188 `print(` calls, several print `cleaned_data`, POST and session data (413-437, 512, 533, 725-729, 765, 814-919, 1225-1312, 1895, 1942-1963, 304, 84-85).
- **Model permission methods** (`publications/models.py`): `Publication.is_editable_by` 490 / `is_deletable_by` 508 and helpers 458/470/482 use the old field names `author`, `supervisor`, `editor` → `AttributeError` for "edit own" users (S4). `Feature.is_editable_by`/`is_deletable_by` 598/615 crash when `created_by`/`modified_by` is None. `Person.is_related_to_user` 162 compares `id_number`/`initials` with `user.username`. Custom permissions: Publication `edit_own_publication`, `delete_own_publication`, `verify_publication` (396); Person `edit_own_person`, `delete_own_person` (96); Feature `edit_own_feature`, `delete_own_feature` (586). No data migration for groups.
- **Login:** `settings.py` CAS 2 (`auth2.dtu.dk`), backends ModelBackend + CASBackend (158), `LOGIN_URL = '/login'` (41) with `FORCE_SCRIPT_NAME = '/find'` → redirect outside `/find/` (FA-R67; the URL name is `cas_ng_login`, `find_artek/urls.py:87`). No CAS signal handler; nothing sets groups. ldap3 is used only in `publications/utils_person.py:580` (`find_ldap_person`, bind with `LDAP_BIND_USER`/`LDAP_BIND_PASSWORD`, `ldaps://win.dtu.dk`), without `memberOf`. Admin login limited to two hard-coded usernames (`publications_meta/views.py`).
- **Form flow:** `ReportFormView.form_valid` 410 stores the raw POST in `session['form_data']`; a PDF is saved at once to `MEDIA_ROOT/temp/<ts>/` as a `FileObject` (`utils_models.py:259`). Optional person workflow (`forms/mixins.py:282`, `workflows/person.py`), review, then `ReportFinalizeView.post` 809 rebuilds the form, saves inside `transaction.atomic()` (853) and copies the temp file into `reports/<year>/` (1100); the temp `FileObject` and file are never deleted. Keywords/topics: `Select2TagWidget` with `data-tags=true` (`forms/publication.py:86-112`) but no code creates new ones; finalize skips unknown pks (940-960). `cleanup_temp_files` command exists, not scheduled.
- **Appendix:** `handle_appendix_file_upload(publication, uploaded_file)` (`utils_models.py:37`) creates `FileObject` without `created_by`/`modified_by`; called from `handle_session_appendix_uploads(request, publication)` 54.
- **Templates:** `base.html` left nav 42-58, mobile menu 148-150; no link to `add_report` or the Excel import anywhere. `report.html`: change-number pencil (86) for any logged-in user; edit/delete/verify (159-166) from `can_*` context; appendix/add feature (188, 213) need `can_edit_publication`.
- **Tests:** `publications/tests.py` is ad-hoc checks against legacy ids (not usable). Usable: `test_upload_appendix_access.py` (`TestCase`, `setUpTestData`, `force_login`, `_app_path()` strips the prefix) and `test_upload_appendix_form.py`. `tests/run.sh:58` `DJANGO_TEST_LABELS` runs those two under `find_artek.settings` against a throwaway MariaDB.
- **Upload limits:** web: nginx `/find/` has `client_max_body_size 300M`, `proxy_read_timeout 120s`; gunicorn gthread, 120 s (2026.2).

## Design notes

- **Permissions in one place.** A module `publications/permissions.py` with a mixin (`PublicationPermissionMixin`, `permission = 'add' | 'edit' | 'delete' | 'verify' | 'manage'`) that requires login (redirect to `LOGIN_URL`) and returns 403 when the check fails. It calls the model methods (`is_editable_by`, `is_deletable_by`, `is_verifiable_by`, `has_perm('publications.add_publication')`) so views, templates and tests share one rule. Function views get a decorator with the same logic.
- **Permission matrix** (decided 2026-11-18: bulk tools for editors only). "Own" = the username equals `id_number` or `initials` of an author, supervisor or editor of the report (`Person.is_related_to_user`, unchanged).

  | Action | Rule | `dtu_user` | `artek_staff` | `artek_editor` |
  |---|---|---|---|---|
  | Add report | `add_publication` | – | yes | yes |
  | Edit report (form, review, finalize, appendix upload) | `change_publication`, or `edit_own_publication` and own | own | own | any |
  | Delete report | `delete_publication`, or `delete_own_publication` and own | – | own | any |
  | Verify / unverify | `verify_publication` | – | – | yes |
  | Change report number, Excel import, bulk delete | `change_publication` (import, number) / `delete_publication` (bulk) | – | – | yes |
  | Add person (form workflow, `add_person_ajax`) | `add_person` | yes | yes | yes |
  | Add feature to a report | `add_feature` and may edit the report | own | own | any |
  | Delete feature | `delete_feature`, or `delete_own_feature` and created it | own | own | any |
  | Edit / delete feature (**changed 2026-11-18, T16**) | `change_feature`/`delete_feature`, or `edit_own_feature`/`delete_own_feature` and listed (author, supervisor, editor) on a report the feature belongs to; the creator alone no longer counts | listed | listed | any |

  Superusers keep everything (Django's `has_perm`). `DeleteReportView`'s rule "creator may delete" is replaced by the matrix (the creator of a report is normally its author or supervisor, so own).
- **Groups by data migration** (`publications/migrations/0003_registration_groups.py`): adds rows to `auth_group` and `auth_group_permissions` only, and is reversible (removes the three groups). It must create the custom permissions first (`create_permissions` for the app, as they are normally made by `post_migrate`). Existing users are **not** touched: they get `dtu_user` at their next login. Effect on live data: three new groups, about 20 new group-permission rows; no existing row changes.
- **Membership at login** (decided 2026-11-18: the AD groups are the only source for `artek_staff` and `artek_editor`; nobody gets them outside the lists): a receiver on django-cas-ng's `cas_user_authenticated` signal in `publications/roles.py`. It adds `dtu_user` always (`dtu_user` is a Django group, not an AD group: "any DTU account that has logged in"). For each of `artek_staff` and `artek_editor`:
  - setting empty (AD group not set up yet): the user is **removed** from the group, so a hand-made assignment in the admin doesn't survive the next login;
  - setting set and the LDAP lookup succeeds: added if member, removed if not;
  - lookup fails (LDAP down, `USE_LDAP = False`): membership from the last successful login is kept, nothing new is granted, a warning is logged.
  Nested AD groups count (LDAP matching rule `1.2.840.113556.1.4.1941`, one query per group, through the existing bind account). Superuser and `is_staff` stay manual and are not touched.
- **Consequence until IT has created the groups:** nobody but superusers can add, verify, renumber or import reports; DTU users can still edit reports they are listed on (`dtu_user`). The release `2026.3` can go live before the lists exist, or wait for them (your choice at T11).
- **New env variables** (empty default = no member): `LDAP_GROUP_ARTEK_STAFF`, `LDAP_GROUP_ARTEK_EDITOR`, each the full DN of the AD group. Go into `.dev.env.example`, `ENVIRONMENT_SETUP.md`, and web_server's `webapp_find_artek.env`.
- **Form flow kept** (decided 2026-11-18). The review and finalize steps re-run the same permission check as the form, the finalize step deletes its temp `FileObject` and file after a successful save (and the old `.old` handling is checked), and the review `post()` uses the right URL names. File moves happen after the database commit (`transaction.on_commit`) so a failed save leaves no half-moved files.
- **Keywords** (decided 2026-11-18): a typed keyword that doesn't exist is created on save by anyone who may edit the report; a typed topic is refused with a form error (topics stay list-only).
- **Verify/unverify move to POST** (forms with CSRF token in `report.html`); a GET shows nothing changed (405).
- **FA-R12 new persons** (decided 2026-11-18): reproduce first on today's code; fix here only if the fix is small and local; otherwise stop and plan FA-R66 directly after 1b. The refactor branch `develop/author_disambiguation/refactor` will conflict in `views.py` either way; that is accepted.
- **User data from AD** (decided 2026-11-18; the Person link was dropped the same day after comparing with the old system, see [old vs new](#old-system-comparison)). The login LDAP lookup in `roles.py` (one bind, already done for the roles) also reads the user's entry: `givenName`, `sn`, `mail` → `auth_user.first_name/last_name/email` at every login (as the old django-auth-ldap `AUTH_LDAP_USER_ATTR_MAP`). Lookup fails → the stored values stay. Effect on live data: `auth_user` rows get name and e-mail at the next login.
  - **No user ↔ Person link.** "Own" keeps the classic rule (username = `Person.id_number` or `initials`), exactly as the old app: it had no link either, and the old database has as few identifiers as today (1004 persons: 196 `id_number`, of which 174 study numbers and 20 employee IDs, 29 initials; today 930 / 194 / 173 / 19 / 26). Staff who maintain the database get `artek_editor`; new persons get study number or initials from LDAP when added (T8). The employee ID is not sensitive (owner, 2026-11-18) and may be stored when there is a use for it.
- **Visibility of person data** (decided 2026-11-18). Institutional e-mails stay public (supervisors must be reachable; a link to the DTU phone book instead is roadmap FA-R71). For anonymous visitors, on the person page and in the person API: `id_number` hidden; `email` hidden when the person is a student (`position` = `student`, or `id_number` like `s` + 6 digits). Logged-in users see both. `phone`, `cell_phone`, `address_1`, `address_2`, `zip_code`, `town`, `state`, `country`, `homepage` are no longer shown or editable anywhere (pages, forms, API, admin); the columns stay until FA-R72 (count, then drop: separate decision).

### Old system comparison

Old (`find_artek_OLD`, tags `v1.*`, `hotfix-1.3.17`): django-auth-ldap, username = `sAMAccountName`/CN (students `sNNNNNN`, staff initials); `givenName`/`sn`/`mail` copied to `auth_user` at every login; `is_staff` from AD group `BYG-ArktiskCenter`; no profile table; user ↔ Person by username = `Person.id_number` or `initials`. LDAP person import: students `id_number` = study number (`name`, `company` = `Studerende`), staff `id_number` = `employeeID`, plus `initials`, `title` → `position`, `department`. Old data: 173 of 196 filled `id_number` are study numbers, ~22 employee IDs, 29 of 1004 persons have initials. New before T12: CAS, only `username` stored, same matching rule.
- **Access to confidential reports:** unchanged for anonymous users. Logged-in users see what they see today. The plan only narrows who may write.
- **Deployment contract:** two new env variables (above); `LOGIN_URL` change (prefix kept under `/find/`); `tests/run.sh` gets new test labels. No change to ports, paths, user, names, entrypoint or cron. web_server needs: the two variables in `webapp_find_artek.env` (may stay empty), and the functional checks of T11.

## Assumptions

- Group names exactly `dtu_user`, `artek_staff`, `artek_editor`; `artek_editor` holds only the extra permissions (every user also has `dtu_user`): `add/change/delete/verify_publication`, `change_person`, `change_feature`, `delete_feature`. `artek_staff`: `add_publication`, `delete_own_publication`. `dtu_user`: `edit_own_publication`, `add_person`, `edit_own_person`, `add_feature`, `edit_own_feature`, `delete_own_feature` (as the old `LDAP_authenticated_user`).
- The CAS username is the DTU study number (`sNNNNNN`, students) or initials (staff), as the LDAP username was. T2 confirmed initials for staff (`thin`); a student login is checked in T11.
- New reports keep `verified = False` (hidden from anonymous users) until an editor verifies them; no change.
- Abandoned temp uploads (form started, never finalized) are not cleaned automatically in 1b; `cleanup_temp_files` stays a manual command (accepted 2026-11-18; roadmap FA-R70, low priority).
- Debug prints that print form, POST or session data are removed; other `print` calls in touched code become `logger.debug`. A full sweep of all 188 is not in scope.
- The admin login whitelist (`publications_meta/views.py`) stays until FA-R59.
- `add_person_ajax` requires `add_person`; `check_person_ajax` and the person workflow steps require login only (read or session).
- The Excel import view gets only the permission check here; its other problems (duplicates, file left in `media/uploads/`) are FA-R57. Exception: the uploaded file is deleted after parsing (S5), since it is a one-line leak fix.

## Tasks

Order: T1 → T2 (you) → T3 → T4 → T5 → T6 → T13 → T16 → T12 → T7 → T8 → T9 → T14 → T10 → T11 (you). T6 is independent and may move.

### T0. Worktree (you or main session)
- `git worktree add -b agent-registration ..\find_artek_agent-registration develop/main` (PowerShell, in `C:\thin\02_Code\docker_projects\find_artek_DEVELOP`). The dev stack runs from `find_artek_DEVELOP`; tests for the branch run in an image built from the worktree (`docker build -t find_artek:registration . && bash tests/run.sh find_artek:registration`) or with the dev stack pointed at the worktree (main session decides; never `down -v`).
- Agent: you (main session).

### T1. Roles: groups and login sync (FA-R54)
- Files: `publications/migrations/0003_registration_groups.py`, `publications/roles.py` (signal receiver, LDAP group lookup), `publications/apps.py` (connect), `find_artek/settings.py` (`LDAP_GROUP_ARTEK_STAFF`, `LDAP_GROUP_ARTEK_EDITOR`, default empty), `.dev.env.example`, `ENVIRONMENT_SETUP.md`, `publications/test_roles.py`.
- Acceptance: migrate on an empty DB creates the three groups with the permissions of the assumptions; migrating back removes them; a CAS login (signal sent in the test) adds `dtu_user`; with a setting empty, a hand-set `artek_staff`/`artek_editor` membership is removed; with a setting and an LDAP answer "member" / "not member", membership is added / removed; LDAP error or `USE_LDAP = False` keeps the previous membership, grants nothing new, and still adds `dtu_user`; superuser and `is_staff` untouched.
- Tests: the above, LDAP mocked (no network); `makemigrations --check` clean.
- Validation: skill `validate` (check, makemigrations --check, `publications.test_roles`, the appendix tests).
- Agent: implementer.
- Deployment impact: two new env variables for `webapp_find_artek.env` (empty allowed).

### T2. Check the CAS username in the dev stack (you)
- After T1 is in the dev stack. Log in at `http://localhost:8098/login` with your DTU account (and, if possible, a student account), then in Git Bash in the repo root:
  ```bash
  DC="docker compose -f docker-compose.yml -f docker-compose.develop.yml"
  $DC exec -T webapp-find-artek python manage.py shell --settings find_artek.development_settings -c "from django.contrib.auth.models import User; u=User.objects.order_by('-last_login').first(); print(u.username, list(u.groups.values_list('name', flat=True)))"
  ```
- Acceptance: the username is your initials (or study number) and the groups list contains `dtu_user`. If the username has another form (e-mail, `@dtu.dk`), stop: "own" needs a mapping, and T3 changes.
- Agent: you.

### T3. Model permission methods (FA-R53, S4)
- Files: `publications/models.py` (`Publication.is_editable_by`, `is_deletable_by`, helpers 458-482, `Feature.is_editable_by`/`is_deletable_by`), `publications/test_permissions_models.py`.
- Acceptance: the rules of the matrix, no `AttributeError` for "own" users, no crash when `created_by` is None; `is_verifiable_by` unchanged.
- Tests: per method: anonymous, plain user, own author / supervisor / editor (by initials and by study number), `dtu_user` not own, `artek_staff`, `artek_editor`, superuser; feature with `created_by` None.
- Validation: `validate`; the new test module and the appendix tests.
- Agent: implementer.
- Deployment impact: none.

### T4. Permission mixin on the report views (FA-R53, S2)
- Files: `publications/permissions.py`, `publications/views.py` (`ReportFormView`, `ReportReviewView`, `ReportFinalizeView`, verify/unverify, `DeleteReportView`, `UploadAppendixView` switched to the mixin), `templates/publications/report.html` (verify/unverify as POST forms, change-number pencil only for editors), `publications/test_report_access.py`.
- Acceptance: every report write view follows the matrix (302 to login for anonymous, 403 when not allowed, 200/redirect when allowed); verify/unverify refuse GET; finalize re-checks the permission, so posting finalize directly without the right fails; the review step's `post()` redirects to existing URLs; no new report becomes visible to anonymous users.
- Tests: one test per view and action for anonymous, `dtu_user` not own, `dtu_user` own, `artek_staff`, `artek_editor`; finalize without permission; verify by GET.
- Validation: `validate`; `publications.test_report_access`, appendix tests.
- Agent: implementer.
- Deployment impact: none.

### T5. Other write views, debug leftovers, appendix user (FA-R53 S3, S5, S6; FA-R68)
- Files: `publications/views.py` (change number, add feature by coordinates / by map, delete feature, `add_person_ajax`, Excel import, bulk delete), `publications/utils_models.py` (`handle_appendix_file_upload(publication, uploaded_file, user)`, from `handle_session_appendix_uploads`), `find_artek/urls.py` (remove `DebugRootView` and `debug-root/`), `views.py` debug prints of form/POST/session data, `templates/publications/report.html` (add-feature button only when allowed), tests in `publications/test_write_access.py` and `test_upload_appendix_access.py` (created_by/modified_by set).
- Acceptance: every view in the "Current state" table follows the matrix; `/debug-root/` is 404; no view prints form, POST or session data; the imported Excel file is removed after parsing; appendix `FileObject`s carry `created_by`/`modified_by`.
- Tests: per view anonymous / not allowed / allowed; `debug-root` 404; appendix upload records the user.
- Validation: `validate`; new modules and appendix tests.
- Agent: implementer.
- Deployment impact: `/find/debug-root/` disappears (public URL removed; it exposed internal paths).

### T6. Login redirect under `/find/` (FA-R67)
- Files: `find_artek/settings.py` (`LOGIN_URL = 'cas_ng_login'`), `development_settings.py` if it overrides it, a test in `publications/test_login_redirect.py` that runs under `find_artek.settings` in `tests/run.sh` and asserts the redirect starts with `/find/login?next=/find/`; `test_upload_appendix_access.py` uses `resolve_url(settings.LOGIN_URL)`.
- Acceptance: production settings redirect to `/find/login?next=...`; dev to `/login?next=...`.
- Validation: `validate`; `tests/run.sh` (settings change) with an image built from the worktree.
- Agent: implementer (small).
- Deployment impact: settings change inside the contract (prefix kept); web: functional check "logged out, a protected URL redirects to `/find/login`".

### T7. Form reliability: PDF, keywords, temp files (FA-R55)
- Files: `publications/views.py` (`ReportFormView`, `ReportFinalizeView._handle_relationships`, `_handle_files`), `publications/forms/publication.py` (keyword field accepts new names, topic field refuses them), `publications/utils_models.py`, `publications/test_report_form.py`, a one-page PDF fixture in `publications/test_fixtures/` (generated, not a real report).
- Acceptance: add a report with title, existing persons, keywords (one new), topic and PDF → report saved with `verified = False`, number assigned, PDF in `reports/<year>/`, temp file and temp `FileObject` gone; edit replaces the PDF; a new topic gives a form error; a failure in finalize leaves no moved files and no half-saved report.
- Tests: the above with `MEDIA_ROOT` in a temp dir (`override_settings`); a PDF of several MB passes the form.
- Validation: `validate`; new module and all 1b modules.
- Agent: implementer.
- Deployment impact: none (PDF upload in production is retested in T11).

### T8. New persons in the form (FA-R12, decision point)
- Files: `publications/test_report_form_persons.py`; if the fix is small: `forms/mixins.py`, `workflows/person.py`.
- Acceptance: a test reproduces "add/edit report form does not properly handle new persons" (readme URGENT) on today's code. Then either a small fix makes it pass, or the agent stops with a written finding (cause, files, estimated size) and the test is kept as `expectedFailure` **only with your approval**, and FA-R66 is planned next.
- Validation: `validate`.
- Agent: implementer; decision by the main session with you.
- Deployment impact: none.

### T9. Menu entries (FA-R56)
- Files: `templates/publications/base.html` (desktop and mobile nav), a context processor or template tag for the permission flags, `publications/test_menu.py`.
- Acceptance: an "Add" menu shows "Add report" to users with `add_publication`, "Import from Excel" to `change_publication` (editors); nothing for anonymous users or plain `dtu_user`.
- Tests: menu rendered for the four user types.
- Validation: `validate`.
- Agent: implementer.
- Deployment impact: none.

### T16. Feature rights follow the report (decided 2026-11-18)
- Files: `publications/models.py` (`Feature.is_editable_by`, `is_deletable_by`: listed on any of `feature.publications` via `Publication.is_own_publication_of`, instead of `created_by`), `publications/permissions.py` if needed, `publications/test_permissions_models.py`, `publications/test_write_access.py`.
- Acceptance: a user listed as author, supervisor or editor on a report the feature belongs to may edit/delete it (with the `*_own_feature` permission, i.e. every `dtu_user`); a logged-in user not listed may not, even if they created the feature; `artek_editor` may edit/delete any; a feature on no report: editors only. Delete buttons in `report.html` follow.
- Tests: the above; T3/T5 tests that encoded "creator may delete" are changed deliberately (say so).
- Validation: `tests/run.sh`.
- Agent: implementer.
- Deployment impact: none.

### T12. User name and e-mail from AD at login
- Files: `publications/roles.py` (the login lookup also reads `givenName`, `sn`, `mail` of the user's entry and sets `first_name`, `last_name`, `email`), `publications/test_roles.py`, `docs`-side: `ENVIRONMENT_SETUP.md` only if the bind account needs a note.
- Acceptance: at a CAS login with a successful lookup, the three fields are set from AD (also when the AD groups settings are empty: one lookup per login, not per group); a failed lookup or `USE_LDAP = False` leaves them unchanged and still adds `dtu_user`; empty AD values don't overwrite stored ones; the roles behaviour of T1 is unchanged; nothing else is stored.
- Tests: the above with LDAP mocked.
- Validation: `tests/run.sh`.
- Agent: implementer.
- Deployment impact: none (same bind account; it must be allowed to read `givenName`, `sn`, `mail`, as the old import did).

### T13. Visibility of person data
- Files: `publications/templates/publications/person.html` and any other template showing person contact data (grep `email`, `id_number`, `phone`, `address`, `homepage`), `api/serializers.py` (`PersonSerializer`, and any nested person data), the person forms in `publications/forms/` and `publications/admin.py` (contact fields removed from forms/admin), `publications/test_person_privacy.py`.
- Acceptance: anonymous: no `id_number` on the person page or in `/api/` person data; student e-mail hidden, staff e-mail shown; logged-in: both shown; the contact fields (`phone`, `cell_phone`, `address_1`, `address_2`, `zip_code`, `town`, `state`, `country`, `homepage`) appear nowhere (page, API, forms, admin) and can't be posted; no column removed.
- Tests: page and API for anonymous / logged-in, student / staff person; a form POST with `phone` doesn't store it.
- Validation: `tests/run.sh`.
- Agent: implementer.
- Deployment impact: none (API output narrower for anonymous users).

### T14. Document: user data and permissions
- Files: `docs/user-data-and-permissions.md` (on the branch: it describes the code), linked from `readme.md`.
- Content: login (CAS, LDAP lookup), what is stored about users (`auth_user` fields, groups; how "own" is matched) and persons (fields, sources, what was removed from view), where it comes from, who sees what (anonymous / logged in / roles; pages and API), the permission matrix and the AD lists, logs, what is not stored (phone, address; `employeeID`), open points (FA-R71, FA-R72, retention, FA-R30 media access).
- Acceptance: matches the code after T12/T13; no secrets, no real personal data.
- Agent: main session (writes from the plan and the code), you review.
- Deployment impact: none.

### T10. Release gate and docs
- Files: `tests/run.sh` (`DJANGO_TEST_LABELS` gains the new modules), `readme.md` (URGENT list, roles: how to give someone `artek_staff` / `artek_editor` in the admin), `ENVIRONMENT_SETUP.md` (checked).
- Acceptance: `docker build -t find_artek:registration . && bash tests/run.sh find_artek:registration` passes in the worktree, all new tests run.
- Validation: `tests/run.sh`, full Django suite of the new modules, `bash -n tests/run.sh`.
- Agent: simple-task (labels, docs); main session reviews.
- Deployment impact: `tests/run.sh` runs more tests (build_image.sh unchanged).

### T11. Release 2026.3 (you)
1. Main session merges `develop/main` into `agent-registration`, reruns the checks, asks you, then `git merge --ff-only agent-registration` on `develop/main`.
2. Roles: when IT has created the AD groups, put their DNs into `LDAP_GROUP_ARTEK_STAFF` / `LDAP_GROUP_ARTEK_EDITOR` (step 3) and add the members in the DTU system. Without them only superusers can add reports; decide whether 2026.3 waits for the lists. Check after the first login as a list member (as T2, against production through the admin user page).
3. Tag, build, publish, deploy as for 2026.2 (`docs/archive/USER_STEPS_release-path_COMPLETE.md` 5d-5g):
   ```powershell
   # PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
   git tag -a 2026.3 -m "find_artek 2026.3: registration (roles, permission checks, report form, menu)" develop/main
   ```
   ```bash
   # WSL
   cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server
   bash scripts/build_image.sh webapp_find_artek /mnt/c/thin/02_Code/docker_projects/find_artek_DEVELOP 2026.3
   ```
   Then copy the bundle to the releases share, set `version: "2026.3"` and `tarball_sha256` in web_server's `ansible/vars/releases.yml`, add `LDAP_GROUP_ARTEK_STAFF=<DN from IT>` and `LDAP_GROUP_ARTEK_EDITOR=<DN from IT>` (empty if not there yet) to `webapp_find_artek.env` (vault), and run `ansible-playbook -kK -i hosts playbook_install_webapp_find_artek.yml -v --ask-vault-pass` (web_server).
4. Functional checks: log in once with a student account: username is `sNNNNNN`, groups `dtu_user`, name/e-mail set (admin user page); logged out, a person page shows no study number and no student e-mail; logged out, `/find/publications/report/add/` → 302 to `/find/login?next=...`; `/find/debug-root/` → 404; as `dtu_user` only, "Add" menu absent and add report 403; as editor, add a test report with a PDF of ~20 MB (retests the production PDF bug, FA-R12/FA-R20), check it is hidden logged out, verify it, then delete it; `media/temp/` empty after finalize.
- Agent: you.

## Out of scope

- FA-R66 (disambiguation refactor), unless T8 shows the fix needs it, then as its own plan.
- FA-R57 (safe Excel import), FA-R58 (person merge), FA-R59 (admin registrations, admin whitelist), FA-R60-65.
- Scheduling `cleanup_temp_files` (cron contract), a general sweep of `print` calls, FA-R10/FA-R30 (media access), Phase 2 coverage targets.
- Any change in dtu_sus_web_server (listed in T11 for you).
- Dropping the Person contact columns (FA-R72), the DTU phone book link (FA-R71), a retention rule for personal data.
- Enforcing "confidential" (field, one rule for pages and lists, PDF access through a checked view): own plan after `2026.3` (FA-R75, FA-R30, FA-R10; decided 2026-11-18). The API lists already follow `publications/visibility.py` (2026.2.1).
- Purging database and `.env` files from git history (FA-R77): own plan, after `2026.2.1`.
