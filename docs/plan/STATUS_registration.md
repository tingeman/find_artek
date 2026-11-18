# Status: Registration (Phase 1b)

Plan: [PLAN_registration.md](PLAN_registration.md). Branch: `agent-registration` (from `develop/main` at `58286e0`), worktree `..\find_artek_agent-registration`.

## Now

T1 (roles: groups and login sync), implementer, in the worktree. Then T2 (you: CAS username check in the dev stack).

## Done

- 2026-11-18: plan written and approved. Decisions: 1b before FA-R66 with the new-person bug reproduced first (T8); keep the session-based form flow; Excel import / change number / bulk delete for `artek_editor` only; new keywords by anyone who may edit the report (topics list-only); `artek_staff`/`artek_editor` **only** from the AD lists (no hand assignment; empty setting = nobody); abandoned temp uploads deferred (FA-R70, low priority).
- T0 2026-11-18: worktree `..\find_artek_agent-registration` on `agent-registration`.

## Open questions

- AD groups requested from IT (2026-11-18): their DNs go into `LDAP_GROUP_ARTEK_STAFF` / `LDAP_GROUP_ARTEK_EDITOR`. Until then only superusers can add reports. Decide at T11 whether 2026.3 waits for them.

## Notes for the next session

- Survey of the write views and their guards is in the plan's "Current state" (line numbers as of `b2cc908`).
- `publications/tests.py` is not a usable test module; new tests go in `publications/test_*.py` modules, style as `test_upload_appendix_access.py`.
- Validation for the worktree: the dev stack runs from `find_artek_DEVELOP` (not the branch). Each task adds its test modules to `DJANGO_TEST_LABELS` in `tests/run.sh` and validates with `docker build -t find_artek:registration . && bash tests/run.sh find_artek:registration` in the worktree (covers check, `check --deploy`, makemigrations --check, migrate on an empty MariaDB, the Django labels).
