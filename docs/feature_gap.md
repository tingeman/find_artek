# Feature gap: find_artek_OLD vs. find_artek (FA-R50)

Written 2026-11-17. Compares the previous version (`C:\thin\02_Code\docker_projects\find_artek_OLD\app-classic\find_artek`, Django 1.6, Python 2, SpatiaLite) with `develop/main` at `9f7e6e6` (Django 4.2, MariaDB). Focus: **getting new reports registered**. Roadmap items are in [roadmap.md](roadmap.md) (FA-R52 to FA-R65).

Sources are cited as `old:` (path below `find_artek_OLD/app-classic/find_artek/`) or `new:` (path below `app-main/`).

How it was checked: by reading the code of both versions, plus anonymous `GET` requests against the local dev stack to see which pages ask for a login. Nothing was submitted and no form was tested in a browser, so "exists" below means "the code is there", not "it works". The uncommitted person-disambiguation work in the tree (`publications/workflows/person_disambiguation.py`, `forms/enhanced.py`, `*.new`) was not reviewed.

## 1. Summary

1. **Registration is not missing, it is unreachable and unfinished.** The new version has an add/edit report form (three steps with a review page), an Excel import, PDF upload, appendix upload, add-feature by coordinates and by map, verify/unverify, change report number and bulk delete. But **no page links to "add report" or to the Excel import**: the old "Administration" menu (`old: publications/templates/publications/add_menu_2.html`) was never ported, so the views can only be reached by typing the URL (`/find/publications/report/add/`, `/find/publications/add/reports_from_file/`). On top of that the readme lists two URGENT production bugs in the form (new persons, PDF upload), and there are no tests for any of it.
2. **Permissions were not ported.** The old version checked Django permissions (`add_publication`, `add_person`, `edit_own_publication`, ...) in every write view. The new write views mostly check only that the user is logged in, and login is DTU CAS, so *any DTU account* counts. This has to be fixed before the entry points are made visible.
3. **One view is open to everybody: appendix upload.** `UploadAppendixView` has no login check at all. See section 2. This is live on the public host and should be fixed before anything else.
4. **Really missing** (no code in the new version): person management (add, edit, delete, **merge**), features from an Excel file, edit feature, file and image upload for features, deleting a single appendix, most of the admin site, the keyword list, the map's feature-type filter, and Danish/English language switching.
5. The Excel import has a **regression**: uploading the same sheet twice now duplicates every report (section 4.2).

## 2. Security findings (act on these first)

Found while comparing; they are in the code that production builds from today.

| # | Finding | Evidence | Effect |
|---|---|---|---|
| S1 | **Appendix upload needs no login.** | `new: publications/views.py:1676` (`class UploadAppendixView(BaseView)`, no `login_required`, no `is_editable_by`). Dev stack: anonymous `GET /publications/report/561/appendix/upload/` returns 200; every other write URL redirects to login. `FileObject.created_by` is nullable, so nothing in the save path needs a user (`new: publications/utils_models.py:37-76`). | Anyone on the internet can attach files (pdf, doc, zip, images, Office files, up to 50 MB each) to any report. They are stored under `media/reports/<year>/<number>/` and served by nginx. Also fills `/tmp` in the container with unsubmitted uploads. Not exploited in this review (no POST was sent). |
| S2 | **Any DTU user can add and edit reports.** | Add: `ReportFormView` and `ReportFinalizeView` check login only (`new: views.py:315, 773`); old checked `add_publication` (`old: publications/views.py:558`). Edit: the only `is_editable_by` check is in the *review page's context* (`new: views.py:501`), where it sets an error text; `ReportFinalizeView.post` saves without any check. | A logged-in DTU user can change title, authors, PDF of any report by posting the form and then the finalize URL. |
| S3 | **Any DTU user can bulk-import, renumber and add features.** | `AddReportsFromFileUploadView` (`views.py:2500`), `ChangeReportNumberView` (`views.py:1852`), `AddFeatureCoordinatesView` (`views.py:1923`), `AddFeatureByMapView` (`views.py:2043`): login only. | As S2. The report page hides the buttons, but the URLs work. |
| S4 | `is_editable_by` / `is_deletable_by` crash for "edit own" users. | `new: publications/models.py:499, 517` use `self.author`, `self.supervisor`, `self.editor`; the fields were renamed to `authors`, `supervisors`, `editors`. | `AttributeError` (HTTP 500 on the report page) for a user who has `edit_own_publication` but not `change_publication`. Today probably nobody has that permission, so it is latent. |
| S5 | Uploaded Excel files stay in public media. | `views.py:2507-2512` writes to `MEDIA_ROOT/uploads/<original name>` and never deletes it. Old deleted the file after parsing (`old: views.py:1432`). | Report lists with student names and numbers reachable under `/find/media/uploads/`. |
| S6 | Debug view and debug output. | `/find/debug-root/` (`new: find_artek/urls.py:36-47, 92`) is public; `views.py` prints form and session data on every request. | Low. Remove with FA-R52. |

Roadmap: **FA-R52** (S1, urgent, one commit on `agent-fixes`) and **FA-R53** (S2-S6).

## 3. Feature comparison

Status: **done** (ported, possibly improved), **partial** (code exists but with gaps), **missing**, **obsolete** (not worth porting).

### 3.1 Registering reports

| Feature | Old | New | Status |
|---|---|---|---|
| Entry point | "Administration" menu with six tiles: add report, add feature, add person, backup, add reports from file, add features from file (`old: add_menu_2.html`, `/pubs/add/`) | none. `base.html` has Frontpage, Map, Reports, Persons, API, login. | **missing** |
| Add/edit report form | one page (`old: views.py:541 add_edit_report`) | three steps: form, optional person disambiguation, review page with changed fields, finalize (`new: views.py:316-1107`) | **partial**: unreachable, URGENT bugs, no permission check, no tests |
| Report number | typed by superusers; normal users get a form without the number field (`old: forms.py:120 UserAddReportForm`) | assigned automatically as `YY-NN` on save (`new: utils_models.py:88`); separate "change number" view that also renames files | **done**, better |
| Authors and supervisors | free text, separated by `;` or `&`; autocomplete; AJAX check with a dialog to choose between database, relaxed and LDAP matches | select2 tag widget plus a multi-step disambiguation workflow (`new: publications/workflows/person.py`, `forms/mixins.py`) | **partial**: readme URGENT bug "does not properly handle new persons"; rework in progress, uncommitted |
| Topics and keywords | tag input; new keywords are created on save, topics only from the list (`old: views.py:622-694`) | select2 over existing rows; the finalize step looks up primary keys only (`new: views.py:944-960`) | **partial**: new keywords probably cannot be created (not tested) |
| PDF upload | in the form; stored as `reports/<year>/<number>.pdf` | same target; uploaded to `media/temp/<timestamp>/` first, moved on finalize (`new: utils_models.py:259`, `views.py:962-1107`) | **partial**: readme URGENT bug "fails during upload of pdf in production"; temp files are never removed (a `cleanup_temp_files` command exists but is not scheduled) |
| Delete or replace PDF | link on the report page / checkbox | checkbox in the edit form | **done** |
| Appendix upload | jQuery multi-uploader with a batch tag (`old: multiuploader/`, `views.py:813`) | session-based multi-file upload (`new: views.py:1676`) | **partial**: S1; a single appendix cannot be deleted (old: `delete_appendixfile`) |
| Excel import of reports | `old: import_from_file.py:61 xlsx_pubs`, form `/pubs/add/pubs_from_file/` | ported to openpyxl (`new: register_from_file.py:34`), form `/publications/add/reports_from_file/` | **partial**: section 4.2 |
| Verify report | `verify_publication` permission; unverified reports hidden from anonymous users | same, plus unverify | **done** |
| Delete report | confirmation page | confirmation page, files removed too; bulk delete with filters | **done**, better |

### 3.2 Persons

| Feature | Old | New | Status |
|---|---|---|---|
| Person list and detail | yes | yes | **done** |
| Add / edit person form | `old: views.py:1943`, `forms.py:159 AddPersonForm` (name parsed into first/middle/prelast/last, collapsible extra fields) | `AddPersonForm` exists in `forms/person.py`, but no view or URL; only an AJAX "add person" used by the report form | **missing** |
| Delete person | `old: views.py:2240` | none | **missing** |
| **Merge persons** | superuser view: lists exact and relaxed matches, moves all author/supervisor/editor relations to the kept person, deletes the others, clears the match flags (`old: views.py:2035`) | none | **missing**, and needed: see 4.3 |
| LDAP lookup by study number or initials | python-ldap | ldap3 (`new: utils_person.py`) | **done** |

### 3.3 Features (map objects)

| Feature | Old | New | Status |
|---|---|---|---|
| Add feature by coordinates | form with easting, northing and 8 reference systems (`old: forms.py:249-281`) | `AddFeatureCoordinatesView` | **done** |
| Add feature on a map | olwidget (OpenLayers 2) digitizing of points, lines, polygons | Leaflet, `AddFeatureByMapView` | **done** (lines and polygons not checked) |
| Edit feature | same views with `feat_id` | none (readme TODO) | **missing** |
| Features from an Excel file | sheet "Features"; preview map; "cancel" deletes the imported features (`old: import_from_file.py:361`, `views.py:1447-1641`) | none | **missing** |
| Files and images on a feature | multi-uploader; images through sorl-thumbnail (`old: views.py:894, 975`) | models and display exist (`new: feature.html:78-90`), no upload | **missing** |
| Delete feature / all features of a report | both | single feature only | **partial** |

### 3.4 Browsing and search

| Feature | Old | New | Status |
|---|---|---|---|
| Report list, report page, person pages, feature page | server-rendered | rendered from the REST API by JavaScript | **done** |
| Search | title, abstract, keywords, comment; by topic; by keyword | title, abstract, keywords; by topic, author, supervisor (`new: api/views.py:74`) | **done** (comment no longer searched, which is right: "confidential" is flagged there) |
| Keyword list page | `/pubs/keywords/list/` | none | **missing** (minor) |
| Overview map | feature-type checkboxes, colour legend, list of the reports with features inside the current map view (`old: views.py:172, 1251 ajax_list_reports`) | map with all features; no type filter or report list found in `static/publications/js/` | **partial** (not checked in a browser) |
| Languages | English and Danish (`LocaleMiddleware`, `publications/locale/da`) | templates use `{% trans %}`, but no locale files or middleware | **missing** (low) |
| REST API with Swagger | none | yes | new |
| PDF thumbnails | none | yes (cron) | new |

### 3.5 Administration

| Feature | Old | New | Status |
|---|---|---|---|
| Django admin | Publication (with author/editor/supervisor inlines), Person, PubType, Topic, Keyword, Feature (map), FileObject (`old: publications/admin.py`) | Publication and Feature only, no inlines (`new: publications/admin.py`); admin login is limited to two hard-coded usernames (`new: publications_meta/views.py`) | **partial**: topics, report types and persons can only be changed in phpMyAdmin |
| Roles from AD groups | on login, AD group membership set the Django groups `ARTEK_staff`, `ARTEK_student`, `LDAP_authenticated_user` and the superuser flag (`old: publications/signals.py`; switched off in 2024) | none: CAS creates a user without any group or permission | **missing**: section 4.4 |
| Database backup button | copied the SQLite file (`old: find_artek/views.py:46`) | handled by the server's backup service | **obsolete** |
| Import of PDFs from the ARTEK FTP server, loading the old road database, BibTeX import | one-off scripts (`old: publications/scripts/`, `import.py`); BibTeX and CSV were menu choices that answered "not implemented yet" | none | **obsolete** |

## 4. How the old version did it

Useful as a specification of behaviour, not as code to copy (Django 1.6 function views, Python 2).

### 4.1 Web form (`old: publications/views.py:541-808`)

- One function view for add and edit. Permission first: `add_publication` to add, `is_editable_by` to edit (`change_publication`, or `edit_own_publication` when the user's username equals the study number or initials of an author, supervisor or editor).
- A `ModelForm` on `Publication` with extra non-model fields: `authors` and `supervisors` (text), `topics` and `keywords` (custom jQuery tag widget, `old: find_artek/widgets.py`), `pdffile`.
- Everything was saved in **one POST**: the publication, then authors and supervisors (all existing relations deleted and rebuilt in the typed order), keywords (created when new), topics, then the PDF. No transaction: a failure halfway left a half-saved report.
- Persons were typed as names. A name could carry a tag: `Jane Doe [id:147]` meant "this database person". Before submit, JavaScript called `check_person_ajax`, which returned a dialog per unclear name with the exact matches, the relaxed matches (name compared without accents and middle names, `first_relaxed`/`last_relaxed` columns) and LDAP matches; the choice was written back into the text field as an `[id:...]` tag. A study number (`s123456`) or initials were looked up in the database, then in LDAP.
- New reports were created with `verified = False` and were invisible to anonymous users until someone with `verify_publication` clicked "verify".

### 4.2 Excel import of reports (`old: publications/import_from_file.py:61-211`)

- Upload form with a file-type choice (only Excel worked). The file was saved to `media/tmp/`, parsed with `xlrd`, and deleted.
- Every sheet with a `title` column was read; the first row holds column names that map directly to `Publication` fields. Special columns: `type` (default `STUDENTREPORT`), `journal`, `author`, `supervisor`, `editor`, `topic`, `keywords`, `URLs`. If `year` was empty it was derived from the report number (`07-12` gives 2007).
- **Idempotent on the report number**: `get_or_create(number=...)`. For an existing report only empty fields were filled, and persons and topics were added only if the report had none. Uploading a corrected sheet again was the normal way of working.
- Persons: study numbers and initials were resolved in the database, then LDAP. For a plain name the import **always created a new Person** and recorded on the relation whether an exact, a relaxed or several matches existed (`exact_match`, `relaxed_match`, `multiple_match` on `Authorship` etc.). Cleaning up was done afterwards with the merge view (4.3).
- Results came back as Django messages, one per problem, plus a count per sheet. No preview, no transaction, no PDFs: files were attached later, by editing each report or with the FTP script.

What the port changed (`new: publications/register_from_file.py`):

- Requires the columns `number, year, title, type, topic, authors, supervisors`; only student-report types are accepted.
- **Regression:** when the number already exists, the row gets the *next free number* and is created as a new report (lines 119-123). The "already exists, fill empty fields" branch can no longer be reached. Uploading the same sheet twice duplicates every report.
- Keeps "always create a new person for a name", but the merge view that this design depends on was not ported.
- The template linked from the page (`publications/docs/ARTEK_report_list.xlsx`) is not in the repository. A test sheet is in `test_files/report_list_TEST_2025.xlsx`.
- S3 and S5 above.

### 4.3 Person merge (`old: publications/views.py:2035-2146`)

Superuser only. For one person the page listed the candidates from the exact and relaxed name match. Selected candidates were merged *into* the current person: their authorships, editorships and supervisorships were re-created for the kept person (keeping the position in the author list), and the candidate was deleted. A "clear flags" button reset the match flags when the person was confirmed to be distinct. Personal fields (e-mail, id number) of the deleted person were lost; the docstring names field-by-field merging as future work.

### 4.4 Roles (`old: publications/signals.py`, `settings.py:210-260`)

Login was LDAP (`django-auth-ldap`). After each login a signal handler put the user into Django groups according to AD group membership: every DTU user got `LDAP_authenticated_user` (edit own publications), members of `BYG-CArtek1_staff` or the course's teacher group got `ARTEK_staff` and `is_staff`, students of course 11427 got `ARTEK_student`, and `BYG-CArtek1_superusers` got `is_superuser`. The permissions themselves were attached to the groups in the admin. The handler was commented out in December 2024 when LDAP login stopped working.

### 4.5 Features from Excel (`old: import_from_file.py:361-679`, `views.py:1447-1641`)

Sheet named `Features` with the columns `Publication_ID, Feature#, Feature_type, Name, Geometry_type, SRID, UTMX/LON, UTMY/LAT, Pos_quality, Date, Description, Comment, Direction`. One row per point; rows sharing a `Feature#` built up a line or polygon. Reachable globally or from a report (then `Publication_ID` had to match). The features were saved immediately and shown on a **validation page with a map**; "cancel" deleted them again, "validate" kept them. Points worked; the code comments mark lines and polygons as unfinished.

## 5. Missing features, ranked

Ranked for the goal "new reports get registered", then by general value. Size: S = one commit, M = a few tasks, L = a plan of its own.

| Rank | What | Why here | Size | Item |
|---|---|---|---|---|
| 0 | Close the anonymous appendix upload (S1) | Live hole on a public host. Independent of everything else. | S | FA-R52 |
| 1 | Permission checks on all write views, and a decision on who may register (S2-S4) | Must be in place before registration is advertised; otherwise every DTU account can edit the database. | M | FA-R53, FA-R54 |
| 2 | Make the report form usable: fix the two URGENT bugs, creating new keywords, temp-file cleanup, tests | The core of the goal. The code exists; it has to be made reliable. | M-L | FA-R55 (with FA-R12) |
| 3 | Entry points: an "Add" menu for permitted users, link to the Excel import and its template | Without it nobody finds the form. Last step of the first batch, after 1 and 2. | S | FA-R56 |
| 4 | Excel import: idempotent again, preview before saving, all-or-nothing, file not kept, permission | Needed for a yearly batch of reports. Dangerous in its current state (duplicates). | M | FA-R57 |
| 5 | Person merge, plus add/edit/delete person | The import creates duplicate persons by design; without merge they accumulate. | M | FA-R58 |
| 6 | Admin site: register Person, PubType, Topic, Keyword, FileObject, with inlines and search | Cheap. Gives a superuser a way to repair any record without phpMyAdmin. Could move up as a stop-gap. | S | FA-R59 |
| 7 | PDFs for imported reports: upload several PDFs named by report number | Neither version attaches PDFs during import; editing 40 reports one by one is the alternative. | M | FA-R60 |
| 8 | Delete a single appendix; delete all features of a report | Small holes in existing pages. | S | FA-R61 |
| 9 | Edit feature | Readme TODO; today a wrong feature must be deleted and re-entered. | M | FA-R62 |
| 10 | Features from Excel, with a preview map | Used for field-course data; less frequent than reports. Depends on the coordinate-transform question (FA-R4). | M-L | FA-R63 |
| 11 | Files and images on features | Models and display exist. | M | FA-R64 |
| 12 | Map filter by feature type, reports in view; keyword list; Danish translation | Display polish. | S-M each | FA-R65 |
| - | Backup button, FTP import, road-database scripts, BibTeX/CSV import | Obsolete or never worked. | - | none |

## 6. Design suggestions for the new implementation

Not decisions; input for the plans.

- **Permissions in one place.** A small mixin (e.g. `PublicationPermissionMixin` with `permission = 'add' | 'edit' | 'delete' | 'verify'`) used by every write view, tested once per view with an anonymous user, a plain DTU user and an editor. This replaces the per-view copies of the old code and the missing ones in the new.
- **Roles.** Simplest: two Django groups created by a data migration (`find_artek editors`: add, change, verify, delete; `find_artek contributors`: add, edit own), membership set by hand in the admin. Automatic membership from AD groups (as the old signal handler did) can come later through the existing ldap3 lookup at CAS login. Whether students register their own reports, or only staff, is the main open question (FA-R54).
- **Keep the review step, drop the session round-trip.** Storing the POST data and a temp file id in the session is where several of the current problems sit (finalize without checks, orphaned temp files, lost state between workers). An alternative is to save the report directly as a *draft* (`verified = False` already hides it from anonymous users) and let the review page be the saved report with "edit" and "verify" buttons. That gives the same safety with ordinary `CreateView`/`UpdateView` code and one transaction.
- **Excel import as preview then commit.** Parse into a list of rows with status (new / update / unchanged / error) and proposed person matches, show it, and write only on confirmation, inside `transaction.atomic()`. Match on report number as the old version did. Parse from the uploaded file object in memory instead of saving it under `media/`.
- **Persons on import: match instead of always creating.** Use the person-matching work in progress (`publications/workflows/`) so that an unambiguous match is linked, and only ambiguous names are flagged for a decision in the preview. Merge is still needed for the existing duplicates.
- **PDF upload in production.** Check the cause before redesigning: one gunicorn sync worker with a 30 s timeout (FA-R20, changed in Phase 1) and write permission of uid 30000 on `media/temp/` on the CIFS share are the two likely ones.
- **Tests with small fixture files** (a three-row `.xlsx`, a one-page PDF) for the form, the import and the permissions. They double as Phase 2 characterization tests.

## 7. Effect on the roadmap order

The roadmap puts feature parity last (Phase 4: after the release path, test coverage and the Django 5.2 upgrade), so that features are written once, on the new version, with tests. Your priority (registering reports now) conflicts with that order. A middle way:

- **FA-R52 now**, as a single fix. It is a security fix, not a feature.
- **Batch A "registration" (FA-R53 to FA-R56) directly after Phase 1**, before or alongside Phase 2. Most of it is fixing, guarding and testing code that already exists, and its tests are Phase 2 tests anyway. It does not add dependencies, so it does not make the Django upgrade harder.
- **Batch B (FA-R57 to FA-R60)** and the rest stay in Phase 4, after the upgrade.

Cost of pulling Batch A forward: the Django upgrade (security support for 4.2 ended April 2026) moves back by the duration of Batch A. This is your decision; the roadmap records it as open.
