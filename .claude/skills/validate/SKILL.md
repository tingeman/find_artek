---
name: validate
description: Run the local checks for find_artek in the dev Docker stack (manage.py check, makemigrations --check, Django tests, bash -n, secrets guard) without secrets or host access, and report them honestly. Use after any change to code, templates, migrations, settings, requirements, Dockerfiles or scripts, and before every commit.
---

# Validate changes locally

Never contact a host, never read `.env` files, never touch the dev data volume. Only these checks.

## 0. The dev stack

The develop compose copies `app-main/` into the image (no source mount), so **rebuild after every code change** before checking:

```bash
cd /c/thin/02_Code/docker_projects/find_artek_DEVELOP
DC="docker compose -f docker-compose.yml -f docker-compose.develop.yml"
$DC up -d --build
$DC ps
```

- `.dev.env` must exist (don't open it). If it is missing, stop and ask me.
- The MariaDB data volume `find-artek-mariadb-dev` is external. If it doesn't exist, compose fails: ask me, don't create it.
- If the stack was not running before you started, stop it again afterwards with `$DC stop` (never `down -v`).
- Requirements changed (`app-main/requirements.txt`): the rebuild installs them. Report the versions pip resolved for the packages you changed (`$DC exec -T webapp-find-artek pip show <pkg>`), since nothing is pinned yet (FA-R2).

## 1. Django system check and migrations

```bash
$DC exec -T webapp-find-artek python manage.py check --settings find_artek.development_settings
$DC exec -T webapp-find-artek python manage.py makemigrations --check --dry-run --settings find_artek.development_settings
```

The second fails if a model changed without a committed migration. For settings or security changes, also run `check --deploy --settings find_artek.settings` and report new findings only (the existing ones are FA-R31).

## 2. Tests

```bash
$DC exec -T webapp-find-artek python manage.py test -v 1 --noinput --settings find_artek.development_settings <app or dotted.path>
$DC exec -T webapp-find-artek python manage.py test -v 1 --noinput --settings find_artek.development_settings   # full suite
```

- Tests run against MariaDB (the GIS fields don't work on SQLite, so `find_artek.test_settings` is not usable). Django creates and drops its own `test_*` database.
- Test modules are `publications/test_*.py` and `api/test_*.py`; helpers in `publications/test_factories.py`. If discovery fails with an import error, report it; don't move or rename test files unless the brief says so.
- If the suite already failed before your change, say which tests, and don't count them against the task.
- Report pass/fail counts and the names of failures, not the raw output.

### 2a. Coverage (optional, dev only)

Only when the brief asks for coverage numbers. `coverage` is in the dev image only (`requirements-dev.txt`); the production image and the release gate `tests/run.sh` don't use it. Configuration: `app-main/.coveragerc` (branch coverage on).

```bash
$DC exec -T webapp-find-artek coverage run manage.py test -v 1 --noinput --settings find_artek.development_settings
$DC exec -T webapp-find-artek coverage report                                   # whole report
$DC exec -T webapp-find-artek coverage report --include='*/publications/visibility.py,*/publications/permissions.py'
```

The suite result of the `coverage run` counts like a normal test run. Report the total and the modules the task touched (statements, missed, branch %), not the whole table.

## 3. Shell scripts

```bash
bash -n scripts/<script>.sh
bash -n tests/run.sh
```

Scripts are copied into the image and run there, so they need LF line endings. `shellcheck` is not installed. Say so.

## 4. Compose and Dockerfiles

`docker compose config` prints the resolved environment, including secrets from `.dev.env`/`.prod.env`: **don't run it**. Read the file instead. For the `Dockerfile` (stages `runtime`/`prod`), check the `deploy-contract` skill and flag every change.

## 4a. Image tests (`tests/run.sh`, the release gate)

Needs no dev stack and no `.dev.env`: it uses a throwaway MariaDB with generated credentials and removes everything afterwards. Run it for Dockerfile, requirements, settings, entrypoint, cron or script changes, and before asking for a release:

```bash
docker build -t find_artek:local .
bash tests/run.sh find_artek:local            # full, ~40-55 s; what build_image.sh runs
bash tests/run.sh --quick find_artek:local    # image checks only, ~10 s
TEST_FILTER='^smoke' bash tests/run.sh find_artek:local
```

Report the last line (`ALL <n> TESTS PASSED` / `<m> OF <n> TESTS FAILED`) and the names of the `FAIL:` lines. `INFO:`/`SKIP:` lines are not failures (e.g. the `check --deploy` warnings W004/W008, FA-R31; `SKIP: django: ...` while `DJANGO_TEST_LABELS` is empty).

## 5. Secrets guard

```bash
git status --porcelain
git diff --cached --name-only | grep -E '(^|/)\.?[a-z]*\.?env$|(^|/)secrets/|password|id_rsa$|\.sqlite3?$' || true
```

No `.env` file (apart from `*.env.example`), no SQLite database, no private key and no media file may be staged.

## Report

List each check as **passed**, **failed** (with the last lines of output) or **not run** (with the reason, e.g. "Docker not running", "`.dev.env` missing"). Never write "passed" for a check that didn't run. Ruff, mypy, pytest and CI are not set up (FA-R40): say so if asked.
