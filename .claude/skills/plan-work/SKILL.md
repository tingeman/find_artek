---
name: plan-work
description: Start or resume a multi-step piece of work on find_artek: write docs/plan/PLAN_<topic>.md and STATUS_<topic>.md in the format used here and in dtu_sus_web_server, link them from docs/roadmap.md (FA-R items), and resume from the status file in a fresh session. Use for any work with several tasks, several subagent runs, or work that spans sessions (e.g. the Django upgrade FA-R1, the download counter FA-R10, the test setup FA-R40). Not for one-commit changes.
---

# Plan and status files

## Start

1. Read `docs/roadmap.md` (on `agent-roadmap` until it is merged: `git show agent-roadmap:docs/roadmap.md`). Find the item the work belongs to (FA-R…).
2. Explore only what the work touches: the code here and, where relevant, the deployment in `dtu_sus_web_server` (`docs/roadmap.md` M5 and FA1–FA5, `docs/deploy/infrastructure.md`, `docker/services/nginx/nginx.conf` for `/find/`, `ansible/playbook_install_webapp_find_artek.yml`). Read those repositories only.
3. Collect open decisions about: migrations and existing data, who can see confidential or unvalidated reports, user-visible behaviour, and anything in the deployment contract (skill `deploy-contract`). Ask them **in one batch**. Minor details get a default under **Assumptions**.
4. Pick `<topic>`: short, lowercase, `-` separated (e.g. `django-5`). The branch will be `agent-<topic>`, from `develop/main` or, when the work belongs to a topic with its own integration branch, from `develop/<topic>/main` (no other base). It merges back into that base.
5. Write both files (templates below). Add or update a row in the roadmap's **Ongoing** table (create the section if missing), pointing to them.
6. Show me the plan and wait for approval, unless I said to go ahead.

## `docs/plan/PLAN_<topic>.md`

```markdown
# Plan: <title>

Status: **draft (<date>)**. Roadmap: <FA-R… items>. Branch: `agent-<topic>` (from `<base branch>`).

## Goal
<numbered outcomes>

## Current state
<only what matters for this work, with file:line references>

## Design notes
<how; migrations and their effect on live data; effect on access to confidential reports; what dtu_sus_web_server must change>

## Assumptions
<defaults picked without asking>

## Tasks
### T0. Test setup    <- only if the code touched has no working tests yet
### T1. <title>
- Files: …
- Acceptance: …
- Tests: <behaviours and edge cases to cover>
- Validation: <skill validate: check, makemigrations --check, which tests>
- Agent: implementer | simple-task | orchestrator | you
- Deployment impact: <none, or what dtu_sus_web_server must change, with the functional checks from its roadmap>

## Out of scope
```

## `docs/plan/STATUS_<topic>.md`

```markdown
# Status: <title>

Plan: [PLAN_<topic>.md](PLAN_<topic>.md). Branch: `agent-<topic>`.

## Now
<one or two lines: what is next, who does it>

## Done
- T1 <date>: <one line> (`<commit>`)

## Open questions
## Notes for the next session
```

Steps only I can run go in the plan as tasks with Agent `you`, with the exact commands: tagging a release, building it (`build_image.sh` in dtu_sus_web_server), deploying, testing against production data, and anything that needs the real `.env` values or the CAS/LDAP login.

## Resume

In a fresh session: read the STATUS file, then the PLAN, then `git status` and `git log --oneline -10` on the branch. Reconcile them; if a task was interrupted, inspect the diff and tell me before discarding anything. Continue at **Now**. Don't re-plan finished tasks.

## Finish

When the last task is done (and released, if the plan includes a release):

1. Mark the roadmap items done (strike-through and **Done <date>**).
2. Read the PLAN ("Out of scope", "Assumptions", design notes that say "later") and the STATUS ("Open questions", "Notes for the next session") for anything deferred or suggested. Put each one into `docs/roadmap.md` as a new FA-R item, or into an existing one. Code comments that say "remove after T<n>" count too. Items for dtu_sus_web_server are listed in the report for me (that repository tracks them in its own roadmap).
3. Archive with `git mv`: `docs/plan/<NAME>_<topic>.md` → `docs/archive/<NAME>_<topic>_COMPLETE.md` for PLAN and STATUS. Update every reference (`grep -rn '_<topic>\.md'` over the repository, including the archived files' links to each other).
4. Remove the row from **Ongoing** and add one to **Finished plans** in the roadmap.
