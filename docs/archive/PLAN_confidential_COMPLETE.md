# Plan: Confidential and unverified reports (FA-R75, FA-R30)

Status: **complete 2026-11-20** (release `2026.4`). Status: [STATUS_confidential_COMPLETE.md](STATUS_confidential_COMPLETE.md), release steps: [USER_STEPS_2026.4_COMPLETE.md](USER_STEPS_2026.4_COMPLETE.md).

Status: **approved 2026-11-19**. Roadmap: FA-R75, FA-R30 (file access), FA-R76 (report API bugs, the detail endpoint must apply the rule). Branch: `agent-confidential` (from `develop/main`), worked in its own worktree `..\find_artek_agent-confidential`. Release: the first release after `2026.3` (e.g. `2026.4`); needs a web_server change (nginx) afterwards.

## Goal

1. `Publication.confidential` is a field. A migration sets it on the reports whose `comment` contains "confidential" (decided 2026-11-18; 2 reports, both unverified today).
2. One rule decides who may see a report, in one module (`publications/visibility.py`), used by every list, page, API endpoint and file:
   - **anonymous**: verified and not confidential;
   - **logged in**: not confidential (verified or not), or confidential and the user is listed on the report (author, supervisor, editor), is in `artek_editor`, or is a superuser.
3. A feature is visible when one of its reports is visible **or it has no report** (decided 2026-11-19: orphan features stay public). A visible feature lists only its visible reports.
4. Report PDFs, appendices, thumbnails and temp uploads are served only after the same check (FA-R30). URLs stay `/find/media/...` (decided 2026-11-19): nginx proxies them to a Django view that checks and answers with `X-Accel-Redirect` to an `internal` nginx location.
5. Anyone who may edit a report may set or clear `confidential` in the add/edit form (decided 2026-11-19).
6. Nothing becomes visible to anonymous users that is hidden today. Data cached in the browser (`sessionStorage`) doesn't survive a login change.

## Current state

- Rule today: `publications/visibility.py:15-23` (`comment__icontains='confidential'` hidden from **everyone**, also superusers and authors; unverified only logged in). Used at `api/views.py:141` (report list), `:191` (feature list/detail), `api/serializers.py:18` (person and feature serializers).
- `api/views.py:30-148` `GetReportViewSet.get_queryset(self, request)`: wrong signature, `/api/report/<pk>/` is always 500; the `q` error branch (`:121`) returns a `Response` (FA-R76).
- `api/views.py:198`: features with no report listed to everyone (kept, goal 3).
- `publications/views.py:401-439` `ReportView`: unverified + anonymous → `access_denied.html` with **status 200**; no confidential check (a confidential verified report is shown with PDF and appendix links to anyone).
- `publications/views.py:1379-1388` `FeatureView`: no check; `feature.html:43` lists every report of the feature; file links at `feature.html:82,88` use a non-existent `filelocation` (broken).
- Files: nginx (web_server `docker/services/nginx/nginx.conf:235`) serves `/find/media/` from the share without a check: every PDF, appendix, thumbnail, `.old` PDF and `temp/` upload is public by URL. Dev serves media via `static()` when `DEBUG` (`find_artek/urls.py:77-79`).
- File layout under `MEDIA_ROOT`: PDF `reports/<year>/<number>[_n].pdf` (`Publication.file` → `FileObject`); appendices `reports/<year>/<number>/<name>` (`Appendenciesship`); thumbnails `reports/<year>/thumbs/<number>_thumb.jpg` (no DB row; `views.py:172-177`, `generate_thumbnails.py:134`); replaced PDFs `<name>.old` (no row, FA-R79); temp uploads `temp/<ts>/...` (`FileObject` with `created_by`); feature files/images (`Feature.files`, `ImageObject`) have no fixed layout.
- Links that point at media: `report.html:58` (thumbnail tag `pubs_extra_tags.py:57-74`), `:114`, `:204`; `upload_appendix.html:120,169,206`; `add_edit_report_review.html:198,202` (`uploaded_file.url` is empty: `FileObject` has no `.url`), `:235`; API `link_to_pdf_associated_with_this_publication` (`api/serializers.py:44`). They all keep their URL under this plan.
- Listed-on-report: `Publication.is_own_publication_of` (`models.py:516`, via `Person.is_related_to_user`: username equals `id_number` or `initials`, case-insensitive, empty never matches). No queryset form yet.
- Browser cache: `my-reports-class.js:240-316` and `my-map-class.js:225-290` cache API results in `sessionStorage`; keys don't include the login state; nothing clears them.
- Tests touching visibility: `api/test_feature_api_reports.py`, `api/test_person_api_reports.py` (comment-based fixtures), `publications/test_report_access.py:139` (`access_denied.html`). No tests for `FeatureView`, the report page with confidential, file access or `/api/report/<pk>/`.

## Design notes

**Field and migration (T1).** `confidential = BooleanField(default=False)`. Migration `0004`: add the column (all existing rows `False`), then a data step that sets `True` where `comment` contains "confidential" (case-insensitive). **Touches existing rows** (decided 2026-11-18): on the live data that is 2 reports; the comment text stays as it is. Reverse: the data step is a no-op, removing the field drops the column. After the migration the comment no longer matters: typing "confidential" into a comment later sets nothing.

**The rule (T2).** `publications/visibility.py` gets:
- `visible_publications(qs, user)`: queryset form, used by every list.
- `can_view_publication(user, publication)`: object form, used by pages and the file view.
- `visible_features(qs, user)` / `can_view_feature(user, feature)`.
- `listed_on_q(user)`: `Q` over authors/supervisors/editors matching `Person.is_related_to_user` exactly (`id_number__iexact` or `initials__iexact` = username, empty values excluded); `.distinct()` where joins duplicate rows. A test pins queryset form and object form to the same answer on a matrix of users and reports.
- `permissions.py` gets an action `VIEW` that delegates to `can_view_publication`, so `PermissionMixin` gives the usual answers: anonymous → login redirect, logged in and not allowed → **404** (the report's existence isn't confirmed).

**API (T2).** Report list, report detail (FA-R76: `get_queryset(self)` with the standard signature; the `q` error becomes a 400 raised as `ValidationError`), person serializer, feature list/detail and the feature's report list all go through the rule. `PublicationSerializer` gains `confidential` (only reports the user may see are serialized anyway).

**Pages (T3).** `ReportView` and `FeatureView` use `VIEW` (status codes above instead of the 200 `access_denied.html`). The feature page lists only visible reports; its file links are fixed to `file.file.url` (they go through T5's check). The report page shows a "Confidential" badge to those who see it.

**Form (T4).** `confidential` checkbox in the add/edit form (anyone who may edit the report; the edit permission check is unchanged), shown on the review step, saved in finalize.

**Files (T5).** A view at `media/<path>` (Django side: `/media/<path>`, public URL `/find/media/<path>`, unchanged):
1. Normalise the path; reject `..`, absolute paths, and anything outside `MEDIA_ROOT` (404).
2. Find the owner: `FileObject` with that `file` name → the report (as PDF via `Publication.file`, as appendix via `Appendenciesship`) or the feature (`Feature.files`); `ImageObject` → feature; `reports/<year>/thumbs/<stem>_thumb.jpg` → the report whose PDF stem or number is `<stem>`; `temp/...` → only the `FileObject.created_by` user, `artek_editor` and superusers.
3. Check with the rule. A file with no owner (e.g. `.old` PDFs, orphans) → 404 for everyone except `artek_editor`/superusers. **Default deny.**
4. Allowed: if `settings.MEDIA_ACCEL_REDIRECT_PREFIX` is set (production default `/find/_protected_media/`), return an empty response with `X-Accel-Redirect: <prefix><path>` and the content type; nginx streams the file (Range requests, caching handled by nginx). If empty (dev settings), return a `FileResponse`. Responses carry `Cache-Control: private` for files that aren't public to anonymous users.
5. Dev: the `static()` media route in `find_artek/urls.py` is replaced by this view, so dev behaves like production.

A read-only command `check_media_access` walks `MEDIA_ROOT` and prints counts per class (report PDF, appendix, thumbnail, feature file, temp, **unowned**) and how many are public / restricted / editor-only; `--list-unowned` prints the unowned paths. You run it on the dev copy before the release (T8) to see what default deny hides.

**Effect on live data and access.** Anonymous users lose access to: confidential reports, pages and files of unverified reports (already hidden as pages, but their files were public), unowned files (`.old`, orphans), temp uploads. Logged-in users without a role lose confidential reports they aren't listed on (they never saw them in lists; the report page and files showed them). Listed persons, `artek_editor` and superusers **gain** confidential reports in the lists (today hidden from everyone). Orphan features stay public.

**Deployment contract (skill `deploy-contract`).** Port, prefix, paths, user, env names unchanged. New, for web_server (after the release is deployed, any order is safe because Django never sees `/find/media/` until nginx sends it):
- remove the `location /find/media/ { alias ... }` block (the existing `/find/` location then proxies media requests to Django);
- add `location /find/_protected_media/ { internal; alias /usr/share/nginx/staticfiles/find_artek_static/media/; }`;
- functional checks: anonymous GET of a public report PDF → 200 `application/pdf`, a Range request → 206; a confidential or unverified report's PDF anonymously → 404; a thumbnail → 200; direct GET of `/find/_protected_media/...` → 404; a slow download of a large PDF that takes longer than 120 s completes (e.g. `curl --limit-rate 200k -o NUL <url>`), and an interrupted one resumes (`curl -C -`).
`MEDIA_ACCEL_REDIRECT_PREFIX` is a plain setting with a production default, not an env variable, so `webapp_find_artek.env` doesn't change.

**Browser cache (T6).** `base.html` renders a login marker (`anon` or a per-session hash, not the user id or name); `base.js` clears the `reportData*`/`featureData*` keys when the marker differs from the stored one. No JS test setup exists (FA-R40): a Django test checks the marker in the page; the JS is checked by hand in the dev stack (T6 acceptance).

## Assumptions

- The person list (`/api/person/`) still lists every person; only their report lists are filtered. A person whose only reports are hidden is still listed by name.
- Report numbers aren't secret: `/api/ajax/next-report-number/` stays as it is.
- Editors' bulk-delete page keeps listing all reports (editors see everything).
- `access_denied.html` stays for other uses if any; `ReportView` no longer uses it.
- No "confidential" badge in the report list JS (the field is in the API for a later badge).
- `report.old.html`, `reports copy.js`, `report_list.html.notused` are left to FA-R41.
- Feature files and images: today's links are broken; fixing them through the checked view is in T3. If no feature has files in the dev copy, T3 records that.

## Tasks

### T0. Worktree (main session)
`git worktree add -b agent-confidential ..\find_artek_agent-confidential develop/main`; copy `.dev.env` into it (ignored); dev stack from the worktree with project name `find_artek_develop` (as in STATUS_registration).

### T1. Field and migration
- Files: `publications/models.py`, `publications/migrations/0004_publication_confidential.py`, `publications/test_confidential_field.py`.
- Acceptance: column added, default `False`; data step sets it on comment matches only; `makemigrations --check` clean; reverse migrates back to `0003`.
- Tests: migration test (`MigrationExecutor`): rows with "Confidential"/"CONFIDENTIAL"/"confidential until" in the comment get `True`, others `False`, comment unchanged.
- Validation: `validate`; full suite (model change).
- Agent: implementer.
- Deployment impact: a migration runs at deploy (adds a column, sets 2 rows). Backup before the release as usual (USER_STEPS).

### T2. The rule and the API (FA-R75, FA-R76)
- Files: `publications/visibility.py`, `publications/permissions.py` (`VIEW`), `api/views.py`, `api/serializers.py`, `api/test_feature_api_reports.py`, `api/test_person_api_reports.py`, new `publications/test_visibility.py`, new `api/test_report_api.py`.
- Acceptance: goal 2 and 3 in every API endpoint; `/api/report/<pk>/` works and 404s for hidden reports; `q` errors give 400; queryset and object forms agree.
- Tests: matrix users {anonymous, `dtu_user` not listed, listed author (by `id_number`), listed supervisor (by initials), listed editor, `artek_staff`, `artek_editor`, superuser} × reports {public, unverified, confidential, confidential+unverified}; features {one public report, hidden only, mixed, none}; empty `id_number`/initials never match. The existing API visibility tests change **deliberately** (comment → field; listed persons and editors now see confidential reports); say so in the commit.
- Validation: `validate`; `api`, `publications.test_visibility`, the T1 test.
- Agent: implementer.
- Deployment impact: none.

### T3. Report and feature pages
- Files: `publications/views.py` (`ReportView`, `FeatureView`), `templates/publications/report.html` (badge), `feature.html` (visible reports only, file links), `publications/test_report_access.py:139` (changes deliberately: login redirect instead of `access_denied.html`), new `publications/test_pages_visibility.py`.
- Acceptance: the matrix from T2 on both pages (anonymous → login redirect when hidden; logged in not allowed → 404); feature page never shows a hidden report's title or link.
- Validation: `validate`; `publications`.
- Agent: implementer.
- Deployment impact: none.

### T4. Confidential in the add/edit form
- Files: `publications/forms/publication.py`, the add/edit/review templates, `ReportFinalizeView`, `publications/test_report_form.py` (new cases).
- Acceptance: checkbox on add and edit; review shows it; finalize saves it; editing another field keeps it; only users who may edit reach the form (unchanged guard).
- Validation: `validate`; `publications.test_report_form`, `publications.test_report_access`.
- Agent: implementer.
- Deployment impact: none.

### T5. Checked file view (FA-R30)
- Files: new `publications/media_access.py` (owner lookup + check), view and URL in `find_artek/urls.py` (replacing the dev `static()` route), `find_artek/settings.py` / `development_settings.py` (`MEDIA_ACCEL_REDIRECT_PREFIX`), `management/commands/check_media_access.py`, `add_edit_report_review.html` (temp file link to `file.file.url`), new `publications/test_media_access.py`.
- Acceptance: design notes "Files" 1-5; path traversal refused; production settings answer with `X-Accel-Redirect` and **no body** (gunicorn never streams a file in production: it has 2 workers × 2 threads and a 120 s timeout, so slow downloads through it would block the app and be cut off), dev settings stream the file.
- Tests (with `override_settings(MEDIA_ROOT=<tmp>)` and small fixture files, never real media): the T2 matrix for PDF, appendix, thumbnail (by number and by PDF stem); temp file for its uploader / another user / editor; unowned and `.old` files; `..`, encoded `%2e%2e`, absolute paths; missing file → 404; header and content type in accel mode; `Cache-Control` on restricted files; the command's counts on a fixture tree.
- Validation: `validate`; `publications.test_media_access`; image tests (`tests/run.sh`, settings change).
- Agent: implementer.
- Deployment impact: **yes**, nginx (design notes "Deployment contract"); the deploy-contract skill and `docs/user-data-and-permissions.md` describe it (T7).

### T6. Browser cache and login changes
- Files: `templates/base.html` (or the base template in use), `static/publications/js/base.js`, `my-reports-class.js`, `my-map-class.js`; a Django test for the marker.
- Acceptance: after logout (or login) in the same tab, lists and map reload from the API; checked by hand in the dev stack with the browser's devtools (sessionStorage before/after).
- Validation: `validate`; the marker test.
- Agent: implementer.
- Deployment impact: none.

### T7. Docs and gate
- Files: `docs/user-data-and-permissions.md` (the rule, files, who sees what), `.claude/skills/deploy-contract/` (media locations), `readme.md` if it mentions media, `tests/run.sh` `DJANGO_TEST_LABELS` (new modules; each task adds its own, T7 checks the list), `ENVIRONMENT_SETUP.md` (no new env var; mention the setting).
- Acceptance: `bash tests/run.sh find_artek:local` passes with all new labels.
- Agent: simple-task (docs), main session (gate check).
- Deployment impact: lists the web_server change for you.

### T8. Release (you)
After `2026.3` is out. Steps in `docs/plan/USER_STEPS_<release>.md` (written when we get there): run `check_media_access` in the dev stack and look at the unowned count; backup; tag; `build_image.sh`; deploy; check the migration (2 rows); then the web_server nginx change and its functional checks (design notes); confirm a confidential PDF is 404 anonymously.

## Out of scope

- Download counter (FA-R10) and statistics (FA-R11): the T5 view is where they can hook in later.
- Cleaning `.old` PDFs (FA-R79) and abandoned temp uploads (FA-R70): T5 only hides them.
- A confidential badge in the report list JS; showing editorships in the person API.
- Hiding persons whose only reports are hidden.
- Leftover templates/JS (FA-R41).
