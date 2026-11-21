# Status: Release 2026.7

Plan: [PLAN_release-2026-7.md](PLAN_release-2026-7.md). Branch: `agent-release-2026-7` (from `develop/main`, worktree `..\find_artek_agent-release-2026-7`).

## Now
T9: dev checks by the owner, step 1 of [USER_STEPS_2026.7.md](USER_STEPS_2026.7.md). Branch tip `5528305` (develop/main merged in): 685 tests, gate 22/22. Added 2026-11-21: T6 Administration page, T7 person markers + confirm, T8 merge; dev checks and release are now T9 and T10.

## Done
- T8 2026-11-21: merge persons (`person/<pk>/merge/`, confirmation page, one transaction, fingerprint against stale confirmations, empty fields filled, INFO log on `publications.persons`); markers link to the merge page; 685 tests, gate 22/22 (`13d253d`). Not filled on merge: hidden contact fields (FA-R72). A report form in progress holding a merged person's pk would fail on save (session data, not handled).
- T9 (main session part) 2026-11-21: develop/main merged in (`5528305`), checks rerun, USER_STEPS_2026.7 written.
- T7 2026-11-21: permission `merge_person` (migration 0005, granted to artek_editor); (!)/(?) markers for holders on the report page (authors, supervisors), report list (API `match` only for holders) and person page notice; `person/<pk>/confirm/` clears the flags; 403 page shows its message again; 661 tests, gate 22/22 (`79cc318`). The report page has no Editors row (never had); marked editor links show only in the person page notice. Marker link URL in two places (`person_marker.html`, `my-reports-class.js`), T8 changes both.
- T6 2026-11-21: Administration page (`publications/administration/`), classic tile order without Backup, greyed tiles with reasons, Django admin tile for staff; header link replaces the drop-down; test_menu.py replaced by test_administration.py; 640 tests (`ec776aa`)
- T5 2026-11-21: `extract_pdf_metadata` (PATH, `--unowned`, `--evaluate N`), pdftotext text layer: title = largest text on page 1, year from report number or front page, study numbers `s` + 6 digits matched to persons; 628 tests (`61616b4`). The agent's final run was killed (low memory); the main session reran all checks.
- T4 2026-11-21: generate_thumbnails exits 1 on errors (CommandError after the summary); gate 22/22 with job.rc 0; 605 tests (`e385e40`). For web_server (report at release): exit code changes; its cron post-check (`ansible/tasks/find_artek_checks.yml:26`) only checks daemon and cron file, unaffected; production logs `exit code 1` nightly until 01-06 and 14-28 are fixed.
- T2b 2026-11-21: option A, no browser cache for the report list and map; `invalidate_feature_cache` flag removed; 603 tests (`e135e46`). Stale sentence in `base.html` comment (mentions the removed report.html cache script): fix in T6.
- T3 2026-11-21: person autocomplete for logged-in users only, anonymous JSON 403; 599 tests (`732b7fc`)
- T2a 2026-11-21: API lists in a fixed number of queries: /api/report/ 1911 -> 4 queries, ~2 s -> ~0.1 s; /api/feature/ 1747 -> 2, ~2.4 s -> ~0.25 s; JSON byte-identical; 595 tests (`3654000`)
- T1 2026-11-21: one 300 MB limit (setting `MAX_UPLOAD_SIZE_MB`), browser check reads it, appendix page shows refusal reasons; 586 tests, gate 22/22 (`c1714c3`)

## Open questions
- (none for T7/T8: decided 2026-11-21, see Notes)
- web_server: does nginx gzip `application/json` on `/find/`? (T2a)
- FA-R86 / FA-R69 data: separate plan after 2026.7 (read-only admin page first, actions after the review).

## Notes for the next session
- Decided 2026-11-21 (person workflow, T7/T8): markers + confirm + merge in 2026.7; markers for editors only (`merge_person`, granted to `artek_editor` by a data migration); merge fills empty fields of the kept person and logs each merge.
- Decided 2026-11-21: Administration page with the classic tiles, unbuilt ones greyed, header link "Administration" (T6); one 300 MB limit for report PDFs and appendices; autocomplete for logged-in users only (anonymous 403); thumbnail job exits 1 on errors; PDF metadata from the text layer first (FA-R98), local LLM later (FA-R99).
- Measured 2026-11-21 (dev copy, anonymous, `manage.py shell` with `CaptureQueriesContext`): `/api/report/` 1911 queries 2.11 s; `/api/feature/` 1747 queries 2.23 s; curl: 172 KB / 660 KB, uncompressed.
- The branch was planned as `agent-post-2026-6` and renamed before it was created (2026-11-21).
- T2b decision 2026-11-21 (main session): **option A, no browser cache**. After T2a the report list takes ~0.1 s and the feature list ~0.25 s server-side (dev copy); a combined cache with browser-side filtering isn't worth its JavaScript. `DATA_VERSION` still added as planned only if it is needed for something else; with A it is not needed for the lists (to confirm when T2b starts). Feature list is 660 KB uncompressed: gzip on web_server's nginx is the remaining lever (open question).
- T2a notes: reports with the same number have no defined order (`-custom_order, -number` has no tiebreak; seen once on the dev copy); not changed. `api/views.py` logs `GetReportViewSet.list was called` at WARNING on every request (noise, FA-R43). New FA-R101 (MultiPoint saved as NULL, to check).
