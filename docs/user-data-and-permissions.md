# User data and permissions

What find_artek stores about users and persons, where it comes from, and who may see and change what. It describes the code on `agent-registration` after T12, T13 and T16 (plan [registration](archive/PLAN_registration_COMPLETE.md)). It also covers T7 (report form), T8 (new persons) and T9 (menu).

Two kinds of people are in the database:

- **Users** (`auth_user`): DTU accounts that have logged in. Used for login, roles and "who created/changed this".
- **Persons** (`publications.Person`): authors, supervisors and editors of reports. Most have never logged in. Users and persons are **not linked** in the database (see [Own reports](#own-reports-how-a-user-is-matched-to-persons)).

## Login

1. `/find/login` (URL name `cas_ng_login`, `LOGIN_URL`) sends the browser to DTU's CAS server (`CAS_SERVER_URL`, CAS 2, with multifactor). django-cas-ng (`AUTHENTICATION_BACKENDS`: `ModelBackend` + `CASBackend`) creates the Django user on the first login. The username is the CAS username: initials for staff, the study number (`sNNNNNN`) for students (staff confirmed in T2, students checked in T11).
2. On every CAS login, `publications/roles.py` (receiver of `cas_user_authenticated`, connected in `publications/apps.py`) does **one** LDAP lookup against DTU's AD (`AUTH_LDAP_SERVER_URI`, bind account `LDAP_BIND_USER` / `LDAP_BIND_PASSWORD`, 5 s timeouts):
   - the user's entry (`sAMAccountName` = username): `givenName`, `sn`, `mail`;
   - membership (nested groups included) of the AD groups in `LDAP_GROUP_ARTEK_STAFF` and `LDAP_GROUP_ARTEK_EDITOR`.
3. From that lookup:
   - the user is put into the Django group `dtu_user` (always, even when the lookup fails);
   - `artek_staff` / `artek_editor`: see [Roles](#roles);
   - `first_name`, `last_name`, `email` are set from `givenName`, `sn`, `mail`. Empty AD values don't overwrite stored ones; names longer than the field are cut, a too long e-mail address is not stored; only changed fields are saved.
4. If the lookup fails (LDAP unreachable, bind error, `USE_LDAP = False`), name, e-mail and AD roles stay as they were and a warning is logged.

`is_superuser` and `is_staff` are never set by the login; they are set by hand. The Django admin (`/find/admin/`, via `admin-cas-login`) is in addition limited to two hard-coded usernames (`publications_meta/views.py`, until FA-R59).

Logout: `/find/logout` (`cas_ng_logout`), also ends the CAS session.

## What is stored

### About users (`auth_user` and related tables)

| Data | Source | When |
|---|---|---|
| `username` | CAS | first login |
| `first_name`, `last_name`, `email` | AD (`givenName`, `sn`, `mail`) | every login (T12) |
| groups `dtu_user`, `artek_staff`, `artek_editor` | login rule / AD groups | every login |
| `last_login`, `date_joined` | Django | login |
| `is_staff`, `is_superuser`, extra permissions | by hand in the admin | – |
| `password` | unusable for CAS users (no password is stored) | – |
| sessions (`django_session`), CAS session tickets (django-cas-ng tables) | Django / django-cas-ng | while logged in |
| `created_by` / `modified_by` on persons, reports, features, files, images | the logged-in user | when a record is saved (appendix uploads since T5) |
| admin change log (`django_admin_log`) | Django admin | admin edits |

Nothing else is read from AD for users. In particular **not stored**: phone numbers, addresses, `employeeID`, department, AD group list. The employee ID is not considered sensitive (decided 2026-11-18) and may be stored later if there is a use for it.

### About persons (`publications.Person`)

| Fields | Content | Source |
|---|---|---|
| `first`, `middle`, `prelast`, `last`, `lineage`, titles, `first_relaxed`, `last_relaxed` | name and its search forms | report form, Excel import, LDAP person lookup (`utils_person.find_ldap_person`) |
| `initials` | staff initials | LDAP lookup, by hand |
| `id_number` | study number (students) or employee ID (staff) | LDAP lookup, import, by hand |
| `email`, `position`, `institution`, `department` | contact and affiliation | LDAP lookup, import, by hand |
| `note`, `quality` | internal | the app / editors |
| `phone`, `cell_phone`, `address_1`, `address_2`, `zip_code`, `town`, `state`, `country`, `homepage` | old contact fields | legacy data only |

The old contact fields (`person_privacy.CONTACT_FIELDS`) are shown and editable nowhere (pages, forms, API; Person is not in the admin). The columns stay until FA-R72 decides to drop them.

New persons from the report form (T8): a name typed as author or supervisor goes through a step where the user picks an existing person or creates a new one. A new person is created only when the report is saved, with the typed name split into name parts and `created_by` set; no study number, initials or e-mail are filled in. Until an editor adds `id_number` or `initials`, such a person matches no user (see [Own reports](#own-reports-how-a-user-is-matched-to-persons)).

## Roles

Three Django groups, created by migration `publications/0003_registration_groups` (data migration: adds the groups and their permission links, changes no existing row; reversible):

| Group | Who | Permissions (app `publications`) |
|---|---|---|
| `dtu_user` | every user who has logged in through CAS | `edit_own_publication`, `add_person`, `edit_own_person`, `add_feature`, `edit_own_feature`, `delete_own_feature` |
| `artek_staff` | members of the AD group in `LDAP_GROUP_ARTEK_STAFF` | `add_publication`, `delete_own_publication` |
| `artek_editor` | members of the AD group in `LDAP_GROUP_ARTEK_EDITOR` | `add_publication`, `change_publication`, `delete_publication`, `verify_publication`, `change_person`, `change_feature`, `delete_feature` |

Every staff member or editor is also in `dtu_user`, so the groups add up.

`artek_staff` and `artek_editor` come **only** from AD (decided 2026-11-18):

- setting empty: nobody has the role; the user is removed from the group at login, so an assignment made by hand in the admin does not survive the next login;
- setting set and lookup succeeded: added if a member of the AD group (nested groups count), removed if not;
- lookup failed: the membership from the last successful login is kept, nothing new is granted.

The settings hold the full DN of the AD group (env variables `LDAP_GROUP_ARTEK_STAFF`, `LDAP_GROUP_ARTEK_EDITOR`, default empty). Until IT has created the groups, only superusers can add, verify, renumber or import reports.

## Own reports: how a user is matched to persons

A user "is" a person when the username equals the person's `id_number` or `initials` (case-insensitive; empty values never match; `Person.is_related_to_user`). This is the rule of the old system; there is no link table (decided 2026-11-18).

- A report is **own** when the user matches one of its authors, supervisors or editors (`Publication.is_own_publication_of`).
- A feature is **own** when it belongs to at least one own report (`Feature.is_own_feature_of`). Who created the feature does not count (T16).

So a student whose person has no study number, or a staff member whose person has no initials, has no own reports. Editors fix that by filling in the identifier.

## Who may do what

The rules live in the model methods (`is_editable_by`, `is_deletable_by`, `is_verifiable_by`) and `publications/permissions.py` (`user_may`, `PermissionMixin`), shared by views, templates and tests. Active superusers may do everything.

| Action | Rule | anonymous | `dtu_user` | `artek_staff` | `artek_editor` |
|---|---|---|---|---|---|
| Add report | `add_publication` | – | – | yes | yes |
| Edit report (form, review, finalize, appendix upload) | `change_publication`, or `edit_own_publication` and own | – | own | own | any |
| Delete report | `delete_publication`, or `delete_own_publication` and own | – | – | own | any |
| Verify / unverify (POST only) | `verify_publication` | – | – | – | yes |
| Change report number, Excel import | `change_publication` | – | – | – | yes |
| Bulk delete | `delete_publication` | – | – | – | yes |
| Add person (form workflow, `add_person_ajax`) | `add_person` | – | yes | yes | yes |
| Add feature to a report | `add_feature` and may edit the report | – | own | own | any |
| Edit / delete feature | `change_feature` / `delete_feature`, or `edit_own_feature` / `delete_own_feature` and own feature | – | own | own | any |

A feature on no report can be changed by editors only.

How a refused request is answered: wrong HTTP method 405, anonymous user redirected to the login with `next`, unknown object 404, logged-in user without the right 403. Ajax endpoints answer JSON 401/403.

Menu: the header's "Add" menu shows "Add report" to users with `add_publication` and "Import from Excel" to users with `change_publication`, the same checks as the views (T9).

The report form (add and edit) has three steps: form, review, finalize; each re-checks the permission. The entered data is kept in the user's session, bound to the form it was entered in (add, or edit of one report), so it can't be saved onto another report. A PDF is stored at once as a temporary upload under `media/temp/` (with `created_by`); finalize only accepts a temporary upload of the same user, moves it to `reports/<year>/` after the database commit and removes the temporary file. A replaced PDF stays on disk as `<name>.old`. Abandoned uploads (form never finished) stay in `media/temp/` until the manual `cleanup_temp_files` command is run (FA-R70). Typed keywords are created when the report is saved; topics can only be chosen from the list (T7).

## Who sees what

### Reports

Who may see a report depends on whether it is verified and whether it is confidential. The table and the rule are in [Confidential and unverified reports](#confidential-and-unverified-reports). The API lists (`/api/report/`, `/api/person/`, `/api/feature/`) follow the same rule (`publications/visibility.py`, `visible_publications`).

### Persons

| Field | anonymous | logged in |
|---|---|---|
| Name, position, institution, department | yes | yes |
| `email` of staff (institutional) | yes | yes |
| `email` of students (`position` = student, or `id_number` = `s` + 6 digits) | **no** | yes |
| `id_number` (study number, employee ID) | **no** | yes |
| Old contact fields (phone, address, homepage) | no | no |

One place for these rules: `publications/person_privacy.py`, used by the person page (`PersonView`), the person API (`/api/person/`), the person list (via the API) and the person autocomplete (searching by study number only when logged in). Institutional e-mails stay public so supervisors can be reached (a DTU phone book link instead is FA-R71).

The person autocomplete (`PersonAutocompleteView`) is public and returns names and ids of all persons for an empty search term (noted in the plan status, out of scope here).

### Users

User data (`auth_user`) is not shown on any public page or in the API. It is visible in the Django admin to superusers.

## Confidential and unverified reports

Two properties decide who may see a report: **verified** (`Publication.verified`, set by an editor) and **confidential** (`Publication.confidential`, a checkbox in the report form). One rule covers the report pages, the feature pages, the API and the files under `/find/media/` (`publications/visibility.py`, `publications/media_access.py`).

| Report | anonymous | logged in, not listed on the report | logged in, listed on the report | `artek_editor`, superuser |
|---|---|---|---|---|
| Verified, not confidential | yes | yes | yes | yes |
| Not verified, not confidential (e.g. a newly added one) | no | yes | yes | yes |
| Confidential, verified or not | no | no | yes | yes |

"Listed on the report" means author, supervisor or editor of it, matched by username as described in [Own reports](#own-reports-how-a-user-is-matched-to-persons).

- **Report and feature pages.** A hidden report sends an anonymous user to the login page; a logged-in user who may not see it gets 404. A feature is shown when it has no report or at least one visible report, and it lists only its visible reports.
- **API.** Hidden reports are not in the lists (`/api/report/`, `/api/person/`, `/api/feature/`), and `/api/report/<id>/` answers 404 for them.
- **Files.** A file under `/find/media/` (report PDF, appendix, thumbnail, feature file or image) is served only to a user who may see the report or feature that owns it. A temporary upload (`media/temp/`) is served only to its uploader and to editors. A file that belongs to no report or feature (old `<name>.old` PDFs, leftovers) is served only to editors and superusers. Any other request for a file gets 404. Django checks the access; in production nginx sends the file (see the deployment contract in `.claude/skills/deploy-contract/SKILL.md`).
- **Browser.** Report and feature data cached in the browser is dropped when the login state changes, so a logged-out browser does not keep showing what a logged-in user saw.

How the flag is set: anyone who may edit a report (see [Who may do what](#who-may-do-what)) can tick "confidential" in the add or edit form. Migration `publications/0004` set the flag once, on the reports whose `comment` contained "confidential" (case-insensitive). The comment text does not count any more: editors set the flag, and should check the flag rather than the comment.

To see how many files of each kind may be downloaded by whom, run `python manage.py check_media_access` (read-only; `--list-unowned` also lists the files that belong to no report).

## Logs

| Log | Content about users | Where |
|---|---|---|
| `publications.roles` warnings | username and the error type when the AD lookup fails (no names, e-mails or LDAP details) | stderr, i.e. the container log (the logger has no handler of its own in `LOGGING`) |
| `debug.log` (`django` logger, INFO) | Django's request and error messages | file in the app directory |
| `api.log` (`api` logger, INFO) | API filtering messages (counts, errors) | file in the app directory |
| nginx access log | IP address, URL, time | `sus-parcweb01`, managed in dtu_sus_web_server |
| CAS / AD | logins | DTU, outside this app |

Debug prints of form, POST and session data were removed in T5. Retention of the log files is not defined here (open point).

## Open points

- **FA-R71**: link persons to the DTU phone book instead of showing staff e-mail addresses.
- **FA-R72**: count the values in the old contact fields, then decide whether to drop the columns (migration on live data).
- **FA-R75, FA-R30**: confidential and unverified reports and the access control for `/find/media/` are implemented on `agent-confidential` (see [Confidential and unverified reports](#confidential-and-unverified-reports)). Open until the release and until web_server's nginx serves `/find/media/` through Django.
- **Retention**: how long inactive `auth_user` rows, sessions and log files are kept; not defined.
- **FA-R59**: replace the hard-coded admin username list.
- AD groups for `artek_staff` / `artek_editor` requested from IT (2026-11-18); until then the settings are empty.
