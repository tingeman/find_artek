# Plan: Django 5.2 LTS upgrade (Phase 3)

Status: **approved (2026-11-21)**. Roadmap: FA-R1 step 2, FA-R3 (Python 3.13), dependency upgrades through the lock (FA-R2 cleanup list). Branch: `agent-django-5` (from `develop/main`). One release: `2026.6`.

## Goal

1. Production runs Django 5.2 LTS (5.2.19 or later, supported until April 2028) on Python 3.13, released as `2026.6` and deployed by web_server.
2. Every direct dependency is on a version that declares Django 5.2 and Python 3.13 support; packages that nothing imports are removed.
3. The suite (538 tests) passes in the dev stack and in `tests/run.sh`. `check --deploy` has no errors and no warnings beyond today's allowed set (FA-R31).
4. No `RemovedInDjango60Warning` from our own code that is cheap to fix, so the next LTS (6.2, FA-R5) starts from a clean base; the rest is listed for FA-R5.

## Current state

- `app-main/requirements.in`: `Django>=4.2,<4.3` (locked 4.2.30), `djangorestframework>=3.14.0,<3.16` (3.15.2), `drf-yasg` 1.21.10, `django-cas-ng` 5.0.1, `django-select2` 8.4.1, `django-extensions` 4.1, `mysqlclient` 2.2.7. Not imported anywhere (grep 2026-11-21): `django-taggit`, `psycopg`, `PyPDF2`, `python-dotenv`, `ping3`.
- Python `3.12.11-slim-bookworm` by digest: `compose.pins.env` `FA_PYTHON_IMAGE`, `Dockerfile:21` `ARG PYTHON_IMAGE` (`tests/run.sh` checks they match). web_server does not pin the find_artek Python image (it builds this Dockerfile).
- Versions on PyPI on 2026-11-21 that support both Django 4.2 and 5.2: DRF 3.16.1, drf-yasg 1.21.18 (classifiers up to 5.2, Python up to 3.13), django-cas-ng 5.1.2 (`Django>=4.2`), django-select2 8.4.8 (last release for Python < 3.14; 8.5+ needs Python 3.14), django-extensions 4.1. Only on 5.2: DRF 3.17/3.18.
- `publications/urls.py:25`: `accounts/logout/` (`publications:logout`) is Django's auth `LogoutView`, which rejects GET from Django 5.0. Nothing links to it; the menu uses `cas_ng_logout` (`find_artek/urls.py:69`, `base.html:114,126,160`). The unused custom `views.LogoutView` (`views.py:1440`) and the commented route (`urls.py:24`) belong to it. Smoke test: `test_smoke_urls.py:151`.
- `find_artek/urls.py:51`: drf_yasg `SWAGGER_USE_COMPAT_RENDERERS` deprecation (found with `-W error::DeprecationWarning` in Phase 1 T11).
- Forms are rendered with `as_table`/`as_p` explicitly (`add_edit_report.html:46`, `login.html:13`), so Django 5.0's div-based default form template doesn't change any page.
- `tests/run.sh:327-333` allows `check --deploy` warnings and prints their IDs as INFO.
- CAS login works from the dev stack (`docs/quick-guides/01_sync_dev_db_from_prod.md:189`), so the login stack can be checked before tagging.

## Design notes

- **Order of commits, each green on its own**: deprecations and logout on 4.2 → drop unused packages → dependency upgrades that still run on 4.2 → Django 5.2 (+ DRF on its newest 5.2 line) → Python 3.13. A regression can be bisected to one step. Only the end state is released.
- **Locks**: every change goes through `requirements.in` + `python scripts/compile_lock.py` with `--exclude-newer 2026-11-07` (two-week cooldown; Django 5.2.19 is from 2026-11-03). Bounds follow FA-R2: Django `>=5.2.19,<5.3`, others lower = the chosen version, upper = next major (DRF held below the next minor that drops 5.2, as with Django's LTS series).
- **Migrations**: none expected. Django 5.x adds no migrations to the contrib apps we use, and our models don't change. If `makemigrations --check` generates a migration, or `showmigrations` lists a new unapplied contrib migration after the upgrade, the task stops and asks: that would touch the live tables.
- **Database**: Django 5.2 supports MariaDB 10.5+ (production 11.2.6) and GDAL 3.1+ (bookworm 3.6). Django 5.2 opens MySQL/MariaDB connections as `utf8mb4` by default. T4 records the database and table character sets of the dev copy (production's schema); if tables are not `utf8mb4`, the effect is described in the report (no conversion in this plan).
- **Access to confidential reports**: unchanged. `publications/visibility.py`, the API serializer filters and the checked media view keep their tests; any change those tests flag is fixed in code, not in the tests.
- **Logout (decided 2026-11-21)**: remove `accounts/logout/`, the custom `views.LogoutView` and the commented route; the smoke-test entry goes with them (deliberate behaviour change). CAS logout (`/logout`) stays the only logout.
- **`check --deploy` (decided 2026-11-21)**: no errors and no new warnings. T1 records today's warning IDs; T6 adds the set to `tests/run.sh` so a new ID fails the gate. FA-R31 stays a separate later item.
- **Deployment contract**: unchanged. Port, `FORCE_SCRIPT_NAME`, paths, uid/gid, env variable names, entrypoint, cron and the `tests/run.sh` interface stay as they are. web_server needs only the usual release bump (`ansible/vars/releases.yml` to `2026.6`). No new env variables.

## Assumptions

- Target Django 5.2 LTS, not 6.x: the roadmap's choice; 6.2 LTS (April 2027) is FA-R5.
- Python 3.13 on Debian 13 trixie (`3.13.x-slim-trixie`, latest patch at T5, by digest). **Changed 2026-11-21 (T4 finding):** the first draft kept bookworm, but Django 5.2.19's new check `gis.W001` warns for GDAL < 3.9 (bookworm 3.6.2; trixie 3.10), and the owner decided "no new `check --deploy` warnings". Fallback if trixie breaks something that can't be fixed in T5: bookworm and `gis.W001` added to the allowed set in T6 (exposure small: the add-feature form casts the SRID to `int` before GDAL). Python 3.14 is not chosen because drf-yasg and python-cas declare up to 3.13.
- `setuptools` stays (removing it is its own question, FA-R2 cleanup list).
- `django-taggit` is removed without a migration: it is not in `INSTALLED_APPS` and no migration refers to it.
- The login stack (CAS + LDAP) stays as it is; only the packages move. The FA-R33 review is not part of this plan.
- Warnings from third-party packages (pyasn1 `tagMap`/`typeMap`, others) are recorded, not patched.
- `.extra()` in `Person.sorted_*` (FA-R92) is left unless Django 5.2 warns about it.

## Tasks

### T0. Worktree (main session)
`git worktree add ..\find_artek_agent-django-5 -b agent-django-5 develop/main`. The dev stack for this plan runs from the worktree (same compose project name, so the external volume `find-artek-mariadb-dev` is shared; only one stack at a time).

### T1. Deprecation audit on 4.2, logout route removed
- Files: `find_artek/urls.py` (drf_yasg compat renderers), `publications/urls.py`, `publications/views.py` (`LogoutView`), `publications/test_smoke_urls.py` (logout entry), any module with a `RemovedInDjango50/51/52Warning`.
- Acceptance: `python -W error::RemovedInDjango50Warning -W error::RemovedInDjango51Warning manage.py test` passes (Django 4.2 has only these classes; later removals are found in T4); `accounts/logout/` resolves to 404; CAS logout unchanged. The report lists today's `check --deploy` warning IDs (from `tests/run.sh` INFO line) and every third-party warning seen.
- Tests: smoke test without the logout entry; a test that `/accounts/logout/` is 404 and `cas_ng_logout` still redirects to the CAS server.
- Validation: `validate`; full suite; `bash tests/run.sh find_artek:local`.
- Agent: implementer.
- Deployment impact: none (a removed, unlinked URL).

### T2. Remove unused packages
- Files: `app-main/requirements.in`, `requirements.txt` and `requirements-dev.txt` (regenerated), readme dependency notes.
- Acceptance: `django-taggit`, `psycopg`, `PyPDF2`, `python-dotenv`, `ping3` no longer in either lock; every other locked version unchanged (`git diff` on the lock shows only removals).
- Validation: `validate` (rebuild); full suite; image tests.
- Agent: simple-task.
- Deployment impact: none.

### T3. Dependency upgrades still on Django 4.2
- Files: `requirements.in`, locks.
- Acceptance: DRF 3.16.1, drf-yasg 1.21.18, django-cas-ng 5.1.2 (pulls python-cas 1.7.x), django-select2 8.4.8; Django still 4.2.30. Swagger (`/swagger/`), ReDoc, the API lists, select2 autocomplete and CAS login/logout URLs keep their tests green; breakages are fixed in code.
- Tests: existing; add a test for any behaviour the upgrade changes (e.g. API pagination or schema output, CAS views' redirect).
- Validation: `validate`; full suite; image tests.
- Agent: implementer.
- Deployment impact: none to the contract. CAS login is checked by you in T8.

### T4. Django 5.2
- Files: `requirements.in` (`Django>=5.2.19,<5.3`, DRF to the newest release declaring 5.2 within the cooldown), locks, code the upgrade breaks, readme.
- Acceptance: suite green; `check` and `makemigrations --check` clean; `showmigrations` lists no new unapplied migration (else stop and ask); `-W error::RemovedInDjango60Warning` run done: cheap fixes in our code made, the rest listed in the report for FA-R5; DB and table charsets of the dev copy recorded (connection now `utf8mb4`).
- Tests: existing suite; tests for any behaviour Django 5.x changed that the suite didn't cover (found while fixing).
- Validation: `validate`; full suite with coverage; image tests.
- Agent: implementer.
- Deployment impact: none to the contract.

### T5. Python 3.13
- Files: `compose.pins.env` (`FA_PYTHON_IMAGE`), `Dockerfile` (`ARG PYTHON_IMAGE`), `docker-compose.develop.yml` if it carries the copy, locks recompiled under 3.13, readme (base-image section).
- Acceptance: `python:3.13.<latest>-slim-trixie@sha256:...` in all copies; system packages (GDAL 3.10, poppler, libmariadb) install under trixie; `check --deploy` no longer reports `gis.W001` (checked by `tests/run.sh`); locks resolve for 3.13; image builds; image size reported against today's.
- Validation: image tests (all); `validate` after rebuilding the dev stack.
- Agent: implementer.
- Deployment impact: none to the contract (the image is self-contained).

### T6. Gate: allowed `check --deploy` warnings
- Files: `tests/run.sh` (`t_check_deploy`: allowed IDs from T1; an ID outside the set fails), its header comment.
- Acceptance: `bash tests/run.sh find_artek:local` passes; with a deliberately added warning (temporary local edit) the check fails.
- Validation: `bash -n tests/run.sh`; image tests.
- Agent: implementer.
- Deployment impact: `build_image.sh` interface unchanged; a new `check --deploy` warning now blocks a release.

### T7. Docs
- Files: `CLAUDE.md` (line 3: Django 5.2; also correct "nginx serves `/find/media/` directly ... Django never sees those requests", outdated since 2026.4's checked media), `readme.md` (versions, release notes for 2026.6), skills that name Django 4.2 or Python 3.12.
- Acceptance: no stale 4.2/3.12 version claims outside history sections.
- Agent: simple-task.
- Deployment impact: none.

### T8. Dev checks (you)
In PowerShell, from `C:\thin\02_Code\docker_projects\find_artek_agent-django-5`:
```powershell
docker compose -f docker-compose.yml -f docker-compose.develop.yml up -d --build
```
At http://localhost:8098/: log in through CAS; check your roles (Add menu visible); add a test report with a PDF and a new person, edit it, delete it; open a confidential report's PDF logged in and logged out; `/swagger/` and `/redoc/` load; the author autocomplete in the report form works; `/admin/` works; CAS logout returns to the front page. Note anything off in the STATUS file or tell the main session.

### T9. Merge and release 2026.6 (you)
Main session: merge `develop/main` into `agent-django-5`, rerun checks, write `docs/plan/USER_STEPS_2026.6.md` (tag, web_server `build_image.sh`, `releases.yml` bump, playbook, production checks: front page and report list under `/find/`, CAS login on `arctic.sustain.dtu.dk`, a confidential PDF logged in / out, `/find/api/` and `/find/swagger/`, thumbnail cron log), then fast-forward `develop/main` with your permission. You tag, build and deploy.

## Out of scope

- Django 6.x (FA-R5); Python 3.14.
- FA-R31 (`check --deploy` warnings, HSTS, `CSRF_TRUSTED_ORIGINS`, `SECRET_KEY` fail-fast).
- FA-R33 (login stack review), FA-R4 (PostgreSQL), MariaDB 11.2 upgrade (web_server).
- Replacing drf-yasg with drf-spectacular (only if T3/T4 show drf-yasg doesn't work on 5.2: then stop and ask).
- FA-R90/FA-R92 cleanups, unless the upgrade forces them.
