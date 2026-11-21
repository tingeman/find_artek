# Plan: Fixes after 2026.6 (upload limit, report list speed and cache, autocomplete access, thumbnail errors, PDF metadata)

Status: **draft (2026-11-21)**. Roadmap: FA-R88, FA-R97, FA-R89, FA-R82, FA-R69 (code part), FA-R98 (step 1). Branch: `agent-post-2026-6` (from `develop/main`). Release: `2026.7`.

Not in this plan: FA-R86 (orphan media files) and the data part of FA-R69. They come later as a separate plan: a read-only admin page first, actions after the review (discussed 2026-11-21). T5's command is input for that plan.

## Goal

1. Report PDFs and appendices up to 300 MB can be uploaded. The browser, the forms and the help texts all say the same limit (FA-R88).
2. The report and feature API lists take a bounded number of queries and well under a second (FA-R97).
3. After a report or feature is added, edited, verified or deleted, the report list and the map show the change without logging out. The browser cache is either dropped or replaced, chosen from the T2a measurements (FA-R89).
4. Anonymous users can't call the person autocomplete any more (FA-R82).
5. When the nightly thumbnail job has errors, it ends with a non-zero exit and the cron wrapper logs a failure (FA-R69, code part).
6. A read-only command reads the first pages of a report PDF's text layer and suggests year, study numbers (with the matching persons) and title. Its accuracy is measured on reports that are in the DB (FA-R98 step 1).
7. Released as `2026.7`.

## Current state

- **Upload limit.** `AddEditReportForm.MAX_FILE_SIZE_MB = 300` (`app-main/publications/forms/publication.py:83`, checked at `:377`). The browser check in `publications/static/publications/js/file-upload.js:27-28` refuses files over 50 MB. That check produced the refusal at the 2026.5 checks. `UploadAppendixForm.clean_appendix_files` limits each appendix to 50 MB (`forms/publication.py:559-565`). `upload_appendix.html:234` tells the user to contact support above 50 MB. nginx allows `client_max_body_size 300M` on `/find/`. gunicorn `--timeout 120` and nginx `proxy_read_timeout 120s` apply (FA-R20). `FILE_UPLOAD_MAX_MEMORY_SIZE` is at its default (2.5 MB), so larger uploads go to a temp file on disk.
- **API speed (measured 2026-11-21, dev copy of production, anonymous).** `/api/report/`: 1911 queries, 2.1-2.5 s, 172 KB, all ~500 reports, no pagination. `/api/feature/`: 1747 queries, 2.2-2.8 s, 660 KB. That's N+1 in `api/serializers.py` (`PublicationSerializer` fields `authors`, `file`, `feature_count`, `link_to_pdf…`; `FeatureSerializer` `related_publications`). The dev stack serves uncompressed JSON. Whether production's nginx gzips JSON hasn't been checked.
- **Report list cache.** `my-reports-class.js:240-312` keeps one API result in `sessionStorage` per filter combination (`reportData_topic_…_author_…`). `my-map-class.js:248-281` does the same for features (`featureData…`). Filters: `topic`, `author_id`, `supervisor_id`, `q` (free text, server side). The list payload holds no topic or person IDs, so it can't be filtered in the browser today. `base.html:29-49` clears the cache when the `auth-marker` meta changes (`publications/context_processors.py:14`, `settings.py:133`). Nothing clears it when the data changes. The session flag `invalidate_feature_cache` (`views.py:437, 1760, 1996`) covers some feature views only. `BaseModel.modified_date` is `auto_now` (`models.py:72`).
- **Autocomplete.** `PersonAutocompleteView` (`views.py:1125`, URL `publications:person-autocomplete`, `urls.py:44`) has no access check. With an empty term it returns every person (`{id, text}`). Only the select2 widgets of the report form use it (`forms/publication.py:116, 129, 443`), and that form needs a login with the right role. Tests that pin the current behaviour: `test_smoke_urls.py:109`, `test_person_privacy.py:170-185`, `test_select2_widgets.py:53`. The dead views from FA-R82 are already gone.
- **Thumbnail job.** `generate_thumbnails` counts errors and prints a summary, but always exits 0 (`management/commands/generate_thumbnails.py:110-122`). `scripts/generate_thumbnails_cron.sh` passes on the exit code and logs `ERROR: thumbnail generation failed with exit code N` when it isn't 0. `tests/run.sh:397` runs the job in the gate and records `job.rc`. In production two publications have no PDF (01-06, 14-28), so the nightly job has 2 errors.
- **PDF tools.** `poppler-utils` is in the runtime image (`Dockerfile:67`, for pdf2image). It includes `pdftotext`: `-f/-l` page range, `-layout`, and `-bbox-layout` with word and line boxes, whose heights stand in for font size. No Python PDF text library is installed (PyPDF2 was removed in 2026.6). `Person.id_number` holds study numbers (`s` + 6 digits). `PersonAutocompleteView.re_studynumber` matches `^s\d{1,6}$`.

## Design notes

- **T1, one limit.** A setting `MAX_UPLOAD_SIZE_MB = 300` in `settings.py`. It's a constant, not an env variable, because it must match nginx's 300M in web_server. Both forms read it, and the help texts and messages show it. The page passes it to the JS (e.g. `data-max-size-mb` on the file input), so `file-upload.js` has no number of its own. The "contact support above 50 MB" note goes. web_server doesn't change.
- **T2a, API queries.** `select_related`/`prefetch_related`/`annotate(Count)` in the API views' querysets, and serializer fields that use the prefetched data. The JSON stays byte-identical: a test compares the response before and after on the same factory data. Confidential and unvalidated filtering stays where it is (`publications/visibility.py`, the serializer), and the tests that pin it stay green unchanged. The implementer reports query counts and times before and after, measured in the dev stack the same way as above (the user runs the measurement if it needs the dev copy's data; the agent may run it against the dev DB but must not read media files). Whether production gzips JSON is a question for web_server (`nginx.conf`, `/find/` location); it's recorded, not changed.
- **T2b, cache decision.** The main session decides from T2a's numbers, then the implementer builds the chosen option:
  - **A, no cache** (default if the full list loads in about 0.3 s or less): remove the `sessionStorage` use from both classes, and fetch fresh data on every page. Stale lists can't happen.
  - **B, one cache, stale-while-revalidate** (if it is still noticeably slow): one full report list and one full feature list per login. The list API adds topic, author and supervisor IDs per report; that only adds IDs to data the user already sees. Topic, author and supervisor filters run in the browser, and `q` stays on the server. The page renders from the cache at once. A data version (below) tells whether it is stale; if it is, the page fetches in the background and redraws.
  - Both options get a **data version**: a context processor `DATA_VERSION`, a short hash of `(count, max(modified_date))` for `Publication` and for `Feature` (two aggregate queries per page), rendered as `<meta name="data-version">`. With A it costs little and still protects the map. With B it is the staleness check. The implementer checks that every write path updates `modified_date` (verify/unverify, number change, appendix upload, authors; `QuerySet.update()` skips `auto_now`). The auth-marker clearing stays.
  - Access is unchanged: a cache only holds what the API gave that user, and it's cleared on login change.
- **T3, autocomplete login.** Anonymous requests get **403** with a JSON body. They don't get a CAS redirect, because select2 calls the URL with XHR. Any logged-in user can search. Decided 2026-11-21. Changing the tests is deliberate: the smoke entry becomes `entry(None, 403, 200, 200, …)`, and `test_anonymous_name_search_still_works` becomes a test that anonymous users get 403.
- **T4, exit code.** After the summary, the command raises `CommandError` (exit 1) when `error_count > 0`. The cron wrapper already logs the failure. **Deployment contract (cron):** the job's exit code changes. web_server's playbook only prints a `docker logs … | grep -F '[thumbnails]'` hint, so nothing breaks there. But production will log the failure every night until 01-06 and 14-28 are fixed. Report this to web_server. The gate must still show `job.rc 0`.
- **T5, PDF metadata (text layer).** A module `publications/pdf_metadata.py` with one function: path → suggestions. It calls `pdftotext` (subprocess, with a timeout, first `--pages` pages, default 3) and needs no new Python dependency.
  - **Study numbers:** `\bs\d{6}\b` (case-insensitive) on all pages read. Each is looked up in `Person.id_number` and the matching person shown.
  - **Year:** `19xx/20xx` candidates from the front page, ranked: the report number in the file name (`96-02` → 1996), a year next to a month or a DTU/BYG/Arctic Technology line, then the most frequent one.
  - **Title:** from `-bbox-layout` on page 1: the lines with the largest height, consecutive, joined. Lines that are only the institution name or a year are skipped.
  - **No text layer** (empty or near-empty text) is reported as "scanned, needs OCR". OCR is FA-R98 later.
  - A management command `extract_pdf_metadata` (read-only): `PATH…` (relative to `MEDIA_ROOT`), or `--unowned` (the orphan files of `check_media_access`), or `--evaluate N`. `--evaluate N` takes N reports that are in the DB and have a PDF and compares title, year and study numbers with the DB. It prints a hit rate per field and lists the misses. That shows whether the text layer is good enough before FA-R86 builds on it.
  - The output contains personal data (names, study numbers). It goes only to the terminal of whoever runs the command; nothing is stored. You run it, on the dev stack's media copy or in production (`docker exec`, read-only). The agents may not read media files (CLAUDE.md), so tests use small PDFs generated in the test.
  - Not exposed on the web in this plan. The prefill of the add-report form and the admin page come later (FA-R98, FA-R86).
- **No migration, no new env variable**, no change to port, paths, user, entrypoint, cron schedule or the `tests/run.sh` interface.

## Assumptions

- One release `2026.7` at the end, with the usual user steps (`docs/plan/USER_STEPS_2026.7.md`, written at T6).
- The 300 MB limit applies to every user who is allowed to upload, per file. An appendix upload with several files can exceed 300 MB in one request; nginx then refuses it with 413, and the page says "per file".
- The JS changes (T1, T2b) are checked by hand in the dev stack (T6). There's no JS test framework (FA-R40).
- T2b defaults to option A unless T2a's numbers say otherwise; the main session states the choice in the status file before T2b starts.
- T5's study-number pattern is `s` + 6 digits (current DTU format). Older formats (e.g. `c`-numbers, 1990s) are listed as misses by `--evaluate` and added if they show up.
- T5's test PDFs are built in the test: a minimal hand-written PDF with a text layer (a few lines in two font sizes), and an image-only PDF from Pillow for the "no text layer" case. Tests that need `pdftotext` are skipped with a clear reason only if the binary is missing (it's in every image, so they run in the dev stack and in `tests/run.sh`).

## Tasks

### T1. One upload limit of 300 MB (FA-R88)
- Files: `app-main/find_artek/settings.py` (`MAX_UPLOAD_SIZE_MB`), `app-main/publications/forms/publication.py` (`AddEditReportForm`, `UploadAppendixForm`), `publications/static/publications/js/file-upload.js`, `publications/templates/publications/add_edit_report.html`, `upload_appendix.html` (and its JS, if it checks size).
- Acceptance: a report PDF or appendix of exactly 300 MB is accepted, and 300 MB + 1 byte is refused with a message that names 300 MB. No 50 MB limit is left in code, JS or templates. The JS reads the limit from the page.
- Tests: form tests for both forms at the limit and above it (patched `size`, or `override_settings(MAX_UPLOAD_SIZE_MB=1)`); the page renders the limit for the JS.
- Validation: skill `validate`: `check`, `makemigrations --check`, full suite (settings change), `docker build` + `bash tests/run.sh find_artek:local`.
- Agent: implementer.
- Deployment impact: none (stays at nginx's 300M).

### T2a. API list endpoints without N+1 (FA-R97)
- Files: `app-main/api/views.py`, `app-main/api/serializers.py`, new tests in `app-main/api/`.
- Acceptance: `/api/report/` and `/api/feature/` use a fixed number of queries, independent of the number of rows. The JSON is the same as before for anonymous, `dtu_user` and `artek_editor`. The measured time on the dev copy is reported (before/after, queries, ms, bytes).
- Tests: `assertNumQueries` with 1 and with 10 reports/features (same count); a snapshot comparison of the JSON on factory data, written before the change; the existing visibility/API tests unchanged.
- Validation: skill `validate`: `api` and `publications` tests, `check`.
- Agent: implementer.
- Deployment impact: none. Open question for web_server: gzip for `application/json` on `/find/`.

### T2b. Report list and map show changes at once (FA-R89)
- Before: the main session picks option A or B from T2a's numbers and records it in the status file.
- Files: `publications/context_processors.py` (`DATA_VERSION`), `find_artek/settings.py` (register it), `publications/templates/publications/base.html`, `publications/static/publications/js/class/my-reports-class.js`, `my-map-class.js`; for B also `api/serializers.py` (IDs per report) and the filter code in the JS; views that change a `Publication` or `Feature` without updating `modified_date` (if any).
- Acceptance: after a report is added, edited, deleted, verified or unverified, its number is changed or an appendix is uploaded, and after a feature is added or deleted, the next page load shows the change (A: always fresh; B: redraw after the background check). The auth-marker behaviour is unchanged (`test_auth_marker.py` green unchanged). B only: changing topic/author/supervisor filters makes no API request once the full list is loaded.
- Tests: `DATA_VERSION` changes after each write path above and stays the same otherwise; bounded queries for the processor (`assertNumQueries`); the head script clears or checks the caches (in the style of `test_auth_marker.py`); B only: the API's new ID fields, also for confidential reports seen by an editor and hidden from anonymous users.
- Validation: skill `validate`: full suite (settings change), `tests/run.sh`.
- Agent: implementer.
- Deployment impact: none.

### T3. Person autocomplete for logged-in users only (FA-R82)
- Files: `app-main/publications/views.py` (`PersonAutocompleteView`), `test_smoke_urls.py:109`, `test_person_privacy.py`, `test_select2_widgets.py` if it calls anonymously.
- Acceptance: anonymous GET gives 403 with a JSON body and no person data, with or without a term. Logged-in users get results as before, including the study-number lookup. The report form's author/supervisor fields still work (T6 by hand).
- Tests: anonymous 403 (empty term, name term, study number); `dtu_user` and `artek_editor` get 200 with results. Existing tests changed deliberately, as in the design notes.
- Validation: skill `validate`: `publications` tests, `check`.
- Agent: implementer.
- Deployment impact: none. Anonymous users can reach less (as decided).

### T4. Thumbnail job exits 1 on errors (FA-R69, code)
- Files: `app-main/publications/management/commands/generate_thumbnails.py`, `app-main/publications/test_management_commands.py`; `tests/run.sh` only if the gate's cron run would now fail (then fix the gate's data, not the expectation).
- Acceptance: with a missing PDF the command prints the summary, then exits 1 (`CommandError`); with no errors it exits 0 as before. Through `generate_thumbnails_cron.sh` an error run logs `ERROR: thumbnail generation failed with exit code 1`, and a clean run logs `completed successfully`. The gate still shows `job.rc 0`.
- Tests: `TestCase` with a publication whose file is missing (`CommandError`, summary printed first); the clean case; `bash -n scripts/generate_thumbnails_cron.sh`.
- Validation: skill `validate`: `publications` tests, `docker build` + `bash tests/run.sh find_artek:local`.
- Agent: implementer.
- Deployment impact: **cron contract**, exit code. Production logs a failure every night until 01-06 and 14-28 are fixed. Listed in the report for web_server.

### T5. Read report metadata from the PDF text layer (FA-R98 step 1)
- Files: new `app-main/publications/pdf_metadata.py`, new `app-main/publications/management/commands/extract_pdf_metadata.py`, new `app-main/publications/test_pdf_metadata.py`. Reuse the unowned-file listing of `check_media_access` (move it into a shared function if needed, without changing that command's output).
- Acceptance: for a PDF with a text layer the command prints title, year and study-number candidates, with the matched persons. For a PDF without one it prints "no text layer". `--unowned` runs over the orphan files. `--evaluate N` prints hit rates for title (normalized comparison), year and study numbers, plus the misses. The command writes nothing (no DB writes, no files) and survives a broken PDF or a `pdftotext` timeout (reported per file, exit 0 unless the arguments are wrong).
- Tests: generated text PDF (title in a large font, `s123456` and a year in small font, two pages, a study number only on page 2 found with `--pages 2` and not with `--pages 1`); image-only PDF → "no text layer"; a study number matched to a factory `Person`; year from the file name; `--evaluate` on two factory reports with generated PDFs; a broken file; no DB writes (`assertNumQueries` read-only, or no row counts changed).
- Validation: skill `validate`: `publications` tests, `check`, `makemigrations --check`.
- Agent: implementer.
- Deployment impact: none (poppler is in the image; nothing new reachable).

### T6. Dev checks and USER_STEPS_2026.7 (main session writes, you check)
- Main session: merge `develop/main` into the branch, rerun the checks, write `docs/plan/USER_STEPS_2026.7.md` in the format of `USER_STEPS_2026.6.md` (dev checks, fast-forward, tag, `build_image.sh`, publish, `releases.yml`, deploy, production checks, after closing).
- You, at http://localhost:8098/ (Ctrl+F5): upload a report PDF and an appendix over 50 MB; the report list and map load fast; delete, add and edit a report and see the change at once without logging out; author autocomplete works logged in; `/publications/test/autocomplete/person/?term=a` logged out gives 403. In the dev container: `python manage.py extract_pdf_metadata --evaluate 50 --settings find_artek.development_settings` and `--unowned`; tell the main session the hit rates (not the personal data).
- Agent: you.

### T7. Release 2026.7 (you)
- Per `USER_STEPS_2026.7.md`: fast-forward `develop/main` (main session, with your OK), tag `2026.7`, `build_image.sh`, publish, `releases.yml`, deploy, production checks. The next morning's thumbnail log shows `exit code 1` with the 2 known errors, as expected until FA-R69's data part is done.
- Agent: you.

## Out of scope

- **FA-R86 and the data part of FA-R69** (orphan and garbled files, the missing PDFs of 01-06 and 14-28): separate plan. A read-only admin page for editors comes first (orphans, broken links, suggested matches, using T5); actions such as rename, link and mark as reviewed come after the review. Delete comes last. Together with FA-R70, FA-R79, FA-R94, which stop new orphans.
- FA-R98 later steps: OCR for scanned PDFs, names next to study numbers, prefilling the add-report form after the PDF upload.
- FA-R99 (local LLM for extraction).
- Removing the `invalidate_feature_cache` session flag (harmless; may go with T2b option A if it becomes dead code, otherwise later).
- Uploads above 300 MB or resumable uploads (nginx changes in web_server).
- Pagination of the API lists (not needed at ~500 reports).
