# Status: Release 2026.7

Plan: [PLAN_release-2026-7.md](PLAN_release-2026-7.md). Branch: `agent-release-2026-7` (from `develop/main`, worktree `..\find_artek_agent-release-2026-7`).

## Now
T2a (API queries) running, implementer, in the worktree. Then T2b (main session picks A or B first). T6 (Administration page, FA-R100) added to the plan 2026-11-21; old T6/T7 are now T7/T8.

## Done
- T1 2026-11-21: one 300 MB limit (setting `MAX_UPLOAD_SIZE_MB`), browser check reads it, appendix page shows refusal reasons; 586 tests, gate 22/22 (`c1714c3`)

## Open questions
- T2b: option A (no cache) or B (one cache, stale-while-revalidate): main session decides from T2a's numbers.
- web_server: does nginx gzip `application/json` on `/find/`? (T2a)
- FA-R86 / FA-R69 data: separate plan after 2026.7 (read-only admin page first, actions after the review).

## Notes for the next session
- Decided 2026-11-21: Administration page with the classic tiles, unbuilt ones greyed, header link "Administration" (T6); one 300 MB limit for report PDFs and appendices; autocomplete for logged-in users only (anonymous 403); thumbnail job exits 1 on errors; PDF metadata from the text layer first (FA-R98), local LLM later (FA-R99).
- Measured 2026-11-21 (dev copy, anonymous, `manage.py shell` with `CaptureQueriesContext`): `/api/report/` 1911 queries 2.11 s; `/api/feature/` 1747 queries 2.23 s; curl: 172 KB / 660 KB, uncompressed.
- The branch was planned as `agent-post-2026-6` and renamed before it was created (2026-11-21).
