# Status: Release 2026.7

Plan: [PLAN_release-2026-7.md](PLAN_release-2026-7.md). Branch: `agent-release-2026-7` (from `develop/main`, worktree `..\find_artek_agent-release-2026-7`).

## Now
T3 (autocomplete login) running, implementer. T2b: option A chosen (see Notes). T6 (Administration page, FA-R100) added to the plan 2026-11-21; old T6/T7 are now T7/T8.

## Done
- T2a 2026-11-21: API lists in a fixed number of queries: /api/report/ 1911 -> 4 queries, ~2 s -> ~0.1 s; /api/feature/ 1747 -> 2, ~2.4 s -> ~0.25 s; JSON byte-identical; 595 tests (`3654000`)
- T1 2026-11-21: one 300 MB limit (setting `MAX_UPLOAD_SIZE_MB`), browser check reads it, appendix page shows refusal reasons; 586 tests, gate 22/22 (`c1714c3`)

## Open questions
- Person disambiguation markers (!/?) and workflow in 2026.7 (owner 2026-11-21): being explored, plan task to be added (FA-R66, FA-R58).
- web_server: does nginx gzip `application/json` on `/find/`? (T2a)
- FA-R86 / FA-R69 data: separate plan after 2026.7 (read-only admin page first, actions after the review).

## Notes for the next session
- Decided 2026-11-21: Administration page with the classic tiles, unbuilt ones greyed, header link "Administration" (T6); one 300 MB limit for report PDFs and appendices; autocomplete for logged-in users only (anonymous 403); thumbnail job exits 1 on errors; PDF metadata from the text layer first (FA-R98), local LLM later (FA-R99).
- Measured 2026-11-21 (dev copy, anonymous, `manage.py shell` with `CaptureQueriesContext`): `/api/report/` 1911 queries 2.11 s; `/api/feature/` 1747 queries 2.23 s; curl: 172 KB / 660 KB, uncompressed.
- The branch was planned as `agent-post-2026-6` and renamed before it was created (2026-11-21).
- T2b decision 2026-11-21 (main session): **option A, no browser cache**. After T2a the report list takes ~0.1 s and the feature list ~0.25 s server-side (dev copy); a combined cache with browser-side filtering isn't worth its JavaScript. `DATA_VERSION` still added as planned only if it is needed for something else; with A it is not needed for the lists (to confirm when T2b starts). Feature list is 660 KB uncompressed: gzip on web_server's nginx is the remaining lever (open question).
- T2a notes: reports with the same number have no defined order (`-custom_order, -number` has no tiebreak; seen once on the dev copy); not changed. `api/views.py` logs `GetReportViewSet.list was called` at WARNING on every request (noise, FA-R43). New FA-R101 (MultiPoint saved as NULL, to check).
