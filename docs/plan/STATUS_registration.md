# Status: Registration (Phase 1b)

Plan: [PLAN_registration.md](PLAN_registration.md). Branch: `agent-registration` (from `develop/main`, not created yet).

## Now

Plan drafted 2026-11-18, waiting for your approval. Then: T0 (worktree), T1 (implementer).

## Done

- 2026-11-18: plan written; decisions: 1b before FA-R66 with the new-person bug reproduced first (T8), keep the session-based form flow, Excel import / change number / bulk delete for `artek_editor` only, new keywords by anyone who may edit the report (topics list-only).

## Open questions

- Who gets `artek_staff` and `artek_editor` at the 2026.3 deploy (T11 step 2).
- AD groups from IT: names/DNs for `LDAP_GROUP_ARTEK_STAFF` and `LDAP_GROUP_ARTEK_EDITOR` (not blocking).

## Notes for the next session

- Survey of the write views and their guards is in the plan's "Current state" (line numbers as of `b2cc908`).
- `publications/tests.py` is not a usable test module; new tests go in `publications/test_*.py` modules, style as `test_upload_appendix_access.py`.
