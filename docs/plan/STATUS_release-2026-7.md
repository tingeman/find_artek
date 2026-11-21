# Status: Release 2026.7

Plan: [PLAN_release-2026-7.md](PLAN_release-2026-7.md). Branch: `agent-release-2026-7` (from `develop/main`, worktree `..\find_artek_agent-release-2026-7`).

## Now
Plan approved 2026-11-21. Branch and worktree created. Next: T1 (implementer) in the worktree.

## Done

## Open questions
- T2b: option A (no cache) or B (one cache, stale-while-revalidate): main session decides from T2a's numbers.
- web_server: does nginx gzip `application/json` on `/find/`? (T2a)
- FA-R86 / FA-R69 data: separate plan after 2026.7 (read-only admin page first, actions after the review).

## Notes for the next session
- Decided 2026-11-21: one 300 MB limit for report PDFs and appendices; autocomplete for logged-in users only (anonymous 403); thumbnail job exits 1 on errors; PDF metadata from the text layer first (FA-R98), local LLM later (FA-R99).
- Measured 2026-11-21 (dev copy, anonymous, `manage.py shell` with `CaptureQueriesContext`): `/api/report/` 1911 queries 2.11 s; `/api/feature/` 1747 queries 2.23 s; curl: 172 KB / 660 KB, uncompressed.
- The branch was planned as `agent-post-2026-6` and renamed before it was created (2026-11-21).
