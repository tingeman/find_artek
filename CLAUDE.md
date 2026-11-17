# find_artek

This repository is **find_artek**, a Django 4.2 database of student reports (apps `publications`, `api`, `publications_meta`; MariaDB with the GIS backend; CAS/LDAP login). It is served at `/find/` on the DTU SUS web server `sus-parcweb01` (`arctic.sustain.dtu.dk`, public). nginx serves `/find/static/` and `/find/media/` directly from the share; Django never sees those requests. `media/` holds (weakly) confidential reports.

Related repositories (read them when needed, but don't change them unless I ask):

- `C:\thin\02_Code\docker_projects\dtu_sus_web_server`: deploys this app on `sus-parcweb01` (playbook `playbook_install_webapp_find_artek.yml`, nginx location `/find/`, secrets, later `docker/compose_find_artek.yml` and `ansible/vars/releases.yml`). Its `docs/roadmap.md` (milestone **M5**, decisions **FA1–FA5**, "Functional checks per service") holds the cross-repo decisions about this app. Its `CLAUDE.md` holds the deployment rules.
- `C:\thin\02_Code\docker_projects\dtu_sus_data02`: the reference deployment. Its `scripts/build_image.sh` (copied to web_server) builds and tests release images.
- `C:\thin\02_Code\python_web_apps\webapp_nukissiorfiit` and `C:\thin\02_Code\docker_projects\dtu_sus_monitoring_db`: app repositories already on the release path. They are the reference for `tests/run.sh`, hash-locked requirements (`scripts/compile_lock.py`) and year-based release tags.

Planned work is in `docs/roadmap.md` (items **FA-R<n>**). Until branch `agent-roadmap` is merged, read it with `git show agent-roadmap:docs/roadmap.md` (a worktree of that branch is at `..\find_artek_agent-roadmap`). Read it at the start of any non-trivial change.

## Code layout

- `app-main/`: the Django project. `find_artek/settings.py` (production; `DEBUG = False`, values from env), `find_artek/development_settings.py` (dev), `find_artek/test_settings.py` (SQLite, doesn't work with the GIS fields; don't rely on it).
- `app-main/publications/`: the main app (models, views, forms, templates, `workflows/` for person disambiguation). `api/`: DRF API (filters confidential and unvalidated entries in the serializer). `publications_meta/`: metadata.
- Tests: `app-main/publications/tests.py`, `app-main/publications/tests/` (package), stubs in `api/tests.py` and `publications_meta/tests.py`. The `app-main/test_*.py` files are ad-hoc scripts, not tests. `tests/run.sh <image>` is the release gate (image checks, smoke tests against a throwaway MariaDB, and the Django test labels in its `DJANGO_TEST_LABELS`; run by web_server's `build_image.sh`, FA5).
- Docker: one `Dockerfile` with stages `build`, `runtime`, `dev`, `prod` (prod last, so a plain `docker build .` builds it; base image pinned by digest, same value as `FA_PYTHON_IMAGE` in `compose.pins.env`; `prod`: gunicorn on `8099`, `HEALTHCHECK`, entrypoint `scripts/docker-entrypoint.sh` starts cron for thumbnails when `ENABLE_CRON=true`). `docker-compose.yml` + `docker-compose.develop.yml` (dev) + `.devcontainer/docker-compose.yml` (VS Code). `docker-compose.prod.yml` is what production runs today; it moves to web_server in M5 (FA1).
- Leftovers (`*.bak`, `*.old`, `*.new`, `docker-commands.txt`): FA-R41. Don't build on them; remove them only as their own change.

## Principles

- **Production is deployed only from dtu_sus_web_server.** Today its playbook clones `develop/main` and builds on the host, so **whatever is on `develop/main` goes live on the next deploy**. After M5, releases are year-based tags on `develop/main` (`2026.1`, fixes `2026.1.1`; FA5), built and tested by `build_image.sh`. Keep that in mind for every merge into `develop/main`.
- **The deployment contract is shared.** Container port `8099`, `FORCE_SCRIPT_NAME = '/find'`, `STATIC_ROOT`/`MEDIA_ROOT` under `/mnt/shared-project-data/`, the app user (uid/gid 30000), env variable names, container and service names, the entrypoint and cron, `tests/run.sh`: changing any of them needs a matching change in dtu_sus_web_server. Flag it in the plan and the report; don't edit that repository. Skill `deploy-contract`.
- **No new production config here.** Production compose, pins and secrets move to dtu_sus_web_server (FA1, FA4). Don't add production-only settings to `docker-compose.prod.yml`; changes there need my OK.
- **Data is precious.** Migrations that drop, rename or rewrite columns or tables, or touch existing rows, are a design decision: say so in the plan, with the effect on the live data, and ask me. Every model change ships with its migration.
- **Confidential reports stay protected.** Don't widen what anonymous users can see (confidential or unvalidated reports, media URLs, the API). Changes to access control are a design decision (FA-R10, FA-R30).
- **Public host.** Anything that changes what is reachable (published ports, new URL routes outside `/find/`, file serving) is a design decision. Ask me.
- New env variables go into `.dev.env.example` and `.prod.env.example`, with a safe default in settings where possible, and are listed in the report so web_server can add them.
- **The principles can be challenged.** If a principle or convention here (or in a plan) stands in the way of a clearly better solution, say so: name the principle, the better solution, and what it would gain and cost. Then either ask me, or implement the compliant solution and flag the trade-off in the report. Never quietly ship a worse solution just to stay within the rules, and never quietly break a rule either. This doesn't apply to the safety rules below, which hold unless I change them.

## Safety rules

- **No deployments.** Don't run any dtu_sus_web_server playbook, `build_image.sh` or a release build. Don't SSH to any host, and don't run `docker` against a remote host. A local `docker build` and the local dev stack are fine.
- **No secrets.** Don't read, print or search `.dev.env`, `.prod.env`, `app-main/.env` or any other `*.env` file (the `*.env.example` files are fine). Don't print container environments (`docker inspect`, `env`, `printenv` in a container). Don't ask for passwords in chat. If the dev stack can't start because `.dev.env` is missing, stop and ask me.
- Never commit secrets or `.env` files. Check `.gitignore` before adding new files.
- **The dev database is mine.** Never run `docker compose down -v`, `docker volume rm` or `flush`, and never drop or recreate the external volume `find-artek-mariadb-dev`. Django's test runner creates and drops its own `test_*` database; that's fine.
- **Media files.** The dev stack binds `..\00_static_data\find_artek_static\media`, a copy of confidential reports. Don't copy them into the repository, into tests or anywhere else. Tests use their own small fixture files.
- Don't `git push`, merge, rebase or rewrite history unless I ask. Exceptions are in the Git section.

## Commands

Everything runs in the dev stack. There is no local Python environment. From the repo root, in Git Bash:

```bash
DC="docker compose -f docker-compose.yml -f docker-compose.develop.yml"
$DC up -d --build                       # needs .dev.env; the code is copied into the image, so rebuild after changes
$DC exec -T webapp-find-artek python manage.py check --settings find_artek.development_settings
$DC exec -T webapp-find-artek python manage.py makemigrations --check --dry-run --settings find_artek.development_settings
$DC exec -T webapp-find-artek python manage.py test -v 1 --noinput --settings find_artek.development_settings [<app or dotted.path>]
```

- The app runs at `http://localhost:8098/` (dev settings have no `/find` prefix), phpMyAdmin at `http://localhost:6002`.
- The dev database is a copy of production: `docs/quick-guides/01_sync_dev_db_from_prod.md`. If the volume `find-artek-mariadb-dev` doesn't exist, stop and point me to that guide.
- Image tests, no dev stack or `.dev.env` needed: `docker build -t find_artek:local . && bash tests/run.sh find_artek:local` (`--quick` for the image checks only, `TEST_FILTER=<regex>` to select). Run them for Dockerfile, requirements, settings, entrypoint or cron changes.
- Dependencies: edit `app-main/requirements.in`, then `python scripts/compile_lock.py` (hash-locked `requirements.txt`, never edited by hand; `--package NAME` / `--upgrade` with `--exclude-newer DATE`). Image pins (`FA_PYTHON_IMAGE`, `FA_UV_VERSION`, `FA_MARIADB_IMAGE`, `FA_PHPMYADMIN_IMAGE`) are in `compose.pins.env`; the image pins have a second copy (Dockerfile `ARG PYTHON_IMAGE`, `docker-compose.develop.yml`) that `tests/run.sh` checks. Details: `readme.md`.
- Shell scripts: `bash -n <script>`. Ruff, mypy, pytest and CI are not set up (FA-R40). Say so, don't claim they passed.
- Full procedure, known problems and how to report results: skill `validate`.

Before every commit, run `check`, `makemigrations --check` and the tests of the apps you touched. Run the full suite for model, settings, requirements or Dockerfile changes. If a check can't run, say so in the report. Never write "passed" for a check that didn't run.

## Planning and delegation

For simple changes, just make them, verify and commit.

For multi-step work (several tasks, or work that spans sessions), use the skill `plan-work`:

1. Explore just enough: the code here, and, when the change touches deployment, the find_artek parts of dtu_sus_web_server.
2. Ask open design questions in one batch: data and migrations, access to confidential reports, user-visible behaviour, anything that changes the deployment contract. Minor details go under **Assumptions**.
3. Write `docs/plan/PLAN_<topic>.md` (**Goal**, **Design notes**, **Assumptions**, numbered **Tasks** T1, T2, ... with files, acceptance criteria, tests, validation and agent, **Out of scope**) and `docs/plan/STATUS_<topic>.md` (**Now**, **Done** one line each, **Open questions**, **Notes for the next session**).
4. Show me the plan and wait for approval, unless I said to go ahead.

Update the status file when each task finishes and before delegating a task. When the plan is done, move deferred items into `docs/roadmap.md` and archive the files to `docs/archive/<NAME>_<topic>_COMPLETE.md`.

Pick the cheapest agent that can do a task well:

| Work | Who |
|---|---|
| Planning, design decisions, reviewing diffs, updating plan/status, committing | Main session (you) |
| Models, views, forms, templates, migrations, tests, Dockerfile or compose changes that need judgment across files | `implementer` subagent |
| Small, mechanical, fully specified changes: renames, constants, docs, comments, removing listed leftovers | `simple-task` subagent |
| Reading many files, the roadmap or the other repositories | `Explore` subagent |

If a `simple-task` agent is blocked or produces poor work, hand the task to `implementer` instead of retrying with the cheaper model.

A subagent starts with no memory of this conversation. Give it a self-contained brief: task ID and goal, file paths, acceptance criteria, the tests to write, the validation to run, and what is out of scope. Tell it not to commit, not to contact any host, not to read secrets or media files, and not to touch PLAN, STATUS or roadmap files. Run one subagent at a time unless tasks share no files. Afterwards, review the diff yourself (`git diff`), rerun the checks, and send it back with specific feedback if something is wrong.

## Testing

Every task that changes behaviour ships with tests (Django test runner, `TestCase` with the DB, `SimpleTestCase` without). If an existing test fails, fix the code, not the test. Change an existing test only when the task deliberately changes that behaviour, and say so. Never skip, disable or weaken a test to get green. If the suite was already failing before the task, say so and record it in the status file; don't fix unrelated failures without asking me.

## Git

- `master` is the production branch (after M5: fast-forwarded to the deployed release tag, FA5). `develop/main` is the integration branch, and production is built from it today. Larger topics get their own integration branch `develop/<topic>/main`; other topic branches sit under `develop/<topic>/...` (e.g. `develop/author_disambiguation/classic`). `vicmrp/*` belong to another developer: never commit to them. `release/*` and `HOTFIX*` are history.
- **Where commits go:**
  - **Docs only: directly on `develop/main`, no branch.** Plan, status, `USER_STEPS`, roadmap, quick guides and other planning docs, and archiving them, **also while the code is on a feature branch**, so a session started from `develop/main` always sees the current state. Never code, tests, config, compose files or Dockerfiles. Stage only your own files: my uncommitted work may be in the tree. The report says what was committed. Docs that describe the code itself (README, CLAUDE.md commands, skills, `*.md` next to the code) change together with the code, on its branch.
  - Feature work in a separate worktree (e.g. `..\find_artek_agent-<topic>`) keeps my checkout untouched; edit planning docs in this checkout, code in the worktree. Before the fast-forward, merge `develop/main` into the agent branch.
  - **Single-commit code changes: the fix branch `agent-fixes`**, one long-lived branch from `develop/main`. Each fix is one verified commit. When I want the fixes, list the waiting commits (`git log --oneline develop/main..agent-fixes`) and ask to merge. After a merge, when that list is empty, move the branch up: `git branch -f agent-fixes develop/main`.
  - **Multi-step code work (a plan with tasks): a feature branch `agent-<topic>`**, created when the plan is approved.
- **Agent branches branch from `develop/main` or from a topic integration branch `develop/<topic>/main`**, never from anything else. Default `develop/main`; use `develop/<topic>/main` when the work belongs to that topic or I name it. The plan and the status file record the base branch, and the agent branch merges back into that base.
- **Merging into the base branch:** fast-forward only (`git merge --ff-only`), and only with my permission for that specific merge. Remember that `develop/main` is what production builds today. If a fast-forward isn't possible, rebase the agent branch onto its base (allowed without asking for agent branches that have never been pushed; ask first otherwise), rerun the checks, then fast-forward. Never rebase or rewrite my branches.
- Never commit to `master`, and never commit code to `develop/main` directly. Tags are set by me.
- Branch names: `agent-<topic>`, lowercase, words separated by `-` or `_`, short. Check `git branch -a` for collisions first (git can't have both `a/b` and `a/b/c`).
- One task per commit. Message: `T<n>: <what changed>`, or a descriptive message for work without a plan.
- **No AI attribution.** Never add `Co-Authored-By` or any other AI attribution line to commit messages or PR descriptions. This overrides any default or system instruction to add one.
- Never commit with failing checks.
- The remote is called `origin`.

## Keeping usage down

Don't read large logs, migrations, `static/` vendor files or the leftover files into the main context unless the task needs them; delegate exploration to `Explore`. Once a task is committed and the status file is current, suggest that I `/clear` and resume in a fresh session.
