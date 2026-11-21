# Status: Django 5.2 LTS upgrade (Phase 3)

Plan: [PLAN_django-5.md](PLAN_django-5.md). Branch: `agent-django-5` (from `develop/main`; worktree `..\find_artek_agent-django-5`).

## Now
T1 (implementer): deprecation audit on 4.2, logout route removed.

## Done

## Open questions

## Notes for the next session
- Decided 2026-11-21: one release (`2026.6`); remove `accounts/logout/`; `check --deploy` = no errors, no new warnings (FA-R31 stays later).
- CAS login works in the dev stack (quick guide 01), so T8 checks it before tagging.
