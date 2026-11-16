# find_artek roadmap

Updated 2026-11-16. Planned work in four phases (below), then the item list (FA-R<n>). The item list was surveyed 2026-11-14 on branch `agent-roadmap`, which this file replaces.

Context: find_artek is a Django 4.2 student-report database (apps `publications`, `api`, `publications_meta`; MariaDB with the GIS backend; CAS/LDAP login). In production it runs behind nginx on sus-parcweb01 under `/find/` (FORCE_SCRIPT_NAME). nginx serves `/find/static/` and `/find/media/` directly from a host mount, so Django never sees PDF downloads (`web: docker/services/nginx/nginx.conf`; `web: docs/deploy/infrastructure.md`). It is deployed by `dtu_sus_web_server`, milestone M5 there (decisions FA1–FA5).

"Source" cites a file in this repo unless prefixed `web:` (= the `dtu_sus_web_server` repo) or `old:` (= `C:\thin\02_Code\docker_projects\find_artek_OLD`, the previous version).

## Ongoing

| Plan | Phase | Branch | Status |
|---|---|---|---|
| [PLAN_release-path.md](plan/PLAN_release-path.md) | 1 | `agent-release-path` | draft, questions open |

## Finished plans

(none yet)

## Phases

Recommended order. Each phase ends with a release (year-based tag, FA5) that web_server deploys, so every step can be rolled back to the previous release.

| # | Phase | Items | Done when |
|---|---|---|---|
| 1 | **Release path and pinning** (deployment refactor, the app side of web: M5) | FA-R2, FA-R3 (pin only), FA-R20, FA-R21, FA-R22, FA-R23, FA-R24, FA-R27, FA-R28; first look at FA-R40 (suite runs) | `tests/run.sh` passes; `build_image.sh` builds release `2026.1` from a tag; web: M5 deploys it; dependencies hash-locked; no published ports; production compose lives in web_server |
| 2 | **Test coverage** | FA-R40, FA-R44; FA-R12 reproduced as failing tests | every URL has a smoke test (anonymous and logged in), the confidentiality filters, forms, uploads and person matching are covered, coverage is measured and meets the target set in the plan; `tests/run.sh` runs the full suite |
| 3 | **Django LTS upgrade** | FA-R1, FA-R3 (Python 3.13), dependency upgrades through the lock | release on Django 5.2 LTS with all dependencies supported, `check --deploy` clean, suite green, deployed |
| 4 | **Feature parity with the previous version** | FA-R50 (analysis), FA-R4 (decide before building), FA-R51, FA-R12, FA-R13 | the gap list is agreed and the chosen features are released |
| later | Downloads, statistics, access control, operations | FA-R10, FA-R11, FA-R30, FA-R25, FA-R26, FA-R31, FA-R42, FA-R43, FA-R5 | separate plans |

Why this order:

1. **Release path first.** Today every deploy clones a moving branch and resolves unpinned dependencies on the host, so even an unrelated redeploy can change what runs, and there is no rollback. Phase 1 freezes what runs today (first release `2026.1` = today's code and today's package versions), so it changes how find_artek is deployed, not what it does. Every later phase then ships as a tested, reversible release. web: M5 waits for it.
2. **Tests before the upgrade.** The risk of a Django major upgrade is silent regressions in views, forms and templates. Characterization tests of today's behaviour (Phase 2) catch them, and `tests/run.sh` makes them a release gate.
3. **Upgrade before features.** Django 4.2 has been out of security support since April 2026, on a public host. New features are written once, on the new version, instead of being ported afterwards. A small, early security step is possible inside Phase 1: the last 4.2.x patch release as `2026.2` (FA-R1 step 1).
4. **Features last, analysis any time.** The analysis of `find_artek_OLD` (FA-R50) is read-only, so it can be pulled forward (e.g. alongside Phase 2) to know the scope early. Decide the database backend (FA-R4) before building GIS-heavy features.

## 1. Dependencies and runtime

| # | Item | Why | Notes/source |
|---|---|---|---|
| FA-R1 | Upgrade Django 4.2 to the current LTS (5.2 LTS, supported until April 2028; the next LTS, 6.2, is due April 2027) | `django==4.2` installs exactly 4.2.0, so the app misses all 4.2.x security patches, and 4.2 itself reached end of support in April 2026. | `app-main/requirements.txt`. Step 1: latest 4.2.x (low risk, possible in Phase 1). Step 2: 5.2 (Phase 3). Blockers: (a) `djangorestframework==3.14.0` needs a release supporting Django 5.x; (b) `drf-yasg` has slow maintenance, check Django 5 support or switch to drf-spectacular; (c) `django-cas-ng`, `django-select2`, `django-taggit`, `django-extensions` need Django 5 compatible versions; (d) `django.contrib.gis` on the MySQL/MariaDB backend (`settings.py:120`) must be verified; (e) duplicate `django.contrib.messages` in INSTALLED_APPS (`settings.py`); (f) tests (Phase 2). Run `python -W error::DeprecationWarning manage.py check` on 4.2 first to surface removals. |
| FA-R2 | Pin the dependencies (**pinning strategy**) | Only Django and DRF are pinned; `Pillow`, `gunicorn`, `mysqlclient`, `PyPDF2`, `ldap3` etc. float to whatever pip resolves at image build, so builds are not reproducible and can break on any redeploy. | As nuki and monitoring_db: direct dependencies in `app-main/requirements.in` with bounds (lower = the version running today, upper = next major; Django held to its LTS series, e.g. `>=4.2.x,<4.3`), a **hash-locked** `requirements.txt` generated by `scripts/compile_lock.py` (uv in the pinned Python image), never edited by hand; dev-only tools in `requirements-dev.in`. The first lock reproduces what production runs today. Upgrades are deliberate: `--package NAME` for one package, `--upgrade` once a year, both with `--exclude-newer` as a cooldown. Later: replace `PyPDF2` (successor `pypdf`), drop `psycopg` if unused, move `werkzeug`/`django-extensions` to dev if not needed in production. `requirements_OLD.txt` goes (FA-R41). |
| FA-R3 | Python and base image | `python:3.12-slim` is not pinned by digest and is rebuilt on every deploy. | `Dockerfile.prod:1`, `Dockerfile.develop:1`. Phase 1: pin today's 3.12.x by digest (`ARG PYTHON_IMAGE` in the Dockerfile and `compose.pins.env`, changed together). Phase 3: 3.13 with FA-R1. |
| FA-R4 | Decide on the database backend | Readme TODO: move to PostgreSQL/PostGIS for coordinate transforms. The GIS-on-MySQL backend has limited functionality. Large change; decide before Phase 4 feature work. | `readme.md` ("Not urgent" list); `settings.py:117-125`. |
| FA-R5 | Next LTS: Django 6.2 | Due April 2027; 5.2 support ends April 2028. | Plan within a year after Phase 3. |

## 2. Features

| # | Item | Why | Notes/source |
|---|---|---|---|
| FA-R50 | **Feature gap analysis against `find_artek_OLD`** (Phase 4, first step; not started) | The previous version had features the current one lacks. Scope must be known before implementing. | `old:`. Output: `docs/feature_gap.md`, one row per feature: what it does in the old version (with source), status here (missing / partial / done differently), user value, rough size, model changes needed, dependency on FA-R4. You pick and order the features; they become FA-R51 tasks. Read-only, can run earlier. |
| FA-R51 | Implement the chosen missing features | Parity with the previous version. | From FA-R50. Batches, each released; tests with every feature. |
| FA-R10 | Per-report download counter | Owner's idea: record (and optionally show) how often each report PDF is downloaded. | Constraint: nginx serves PDFs directly from `/find/media/`, so Django never sees the request. Options: (A) route downloads through a Django view that counts, then returns an `X-Accel-Redirect` header so nginx still streams the file from an `internal;` location; (B) count from nginx access logs. **Recommended: A.** Details: new view e.g. `/find/download/<id>/`; the report template links to it instead of `file.url`; needs an `internal` location in nginx (change in the `web:` repo) and the direct `/find/media/` path must stop being publicly reachable for PDFs, otherwise the counter can be bypassed. Count once per IP per day (hash of IP+UA+date, not the raw IP). Store as a counter field or a small `DownloadCount(report, day, n)` table. Optionally show the count on the report page. A view can also enforce the confidentiality checks (FA-R30). |
| FA-R11 | Long-term usage statistics | Document usage over time (page views, searches, downloads) for reporting. | Aggregate per day into a small table (date, metric, optional report id, count). No raw IPs stored long-term. Download counts come from FA-R10. Align with the cross-app usage-statistics approach planned in `web:` before building anything here. |
| FA-R12 | Fix known production form bugs | Readme lists two URGENT items: add/edit report form mishandles new persons not yet in the database; PDF upload fails in production. | `readme.md` ("URGENT"). The upload failure may be the 30 s gunicorn timeout or the single worker (FA-R20, Phase 1). The person handling is the subject of the person-disambiguation work in progress (`publications/workflows/`, uncommitted on 2026-11-16). Reproduce both as tests in Phase 2. |
| FA-R13 | Smaller readme TODOs | "Add feature" button shown when logged out; duplicate acknowledgement pop-ups; edit-feature view; compare data and models with the old find-artek. | `readme.md`; `app-main/api/views.py:80-81` (TODO: show unvalidated/confidential entries to validated/admin users). The comparison with the old version is FA-R50. |
| FA-R14 | DB query at import time in the API | `GetReportViewSet` builds its Swagger description with `Topic.objects.all()` when the class is defined, so importing the URLconf needs the table: `check`, `migrate` and tests fail on an empty database (fresh install, tests), and the topic list in the API docs is frozen at process start. | `app-main/api/views.py:33-46`. Build the description lazily (or drop the topic list from it). Found in Phase 1 T1; `tests/run.sh` works around it with `migrate --skip-checks`. Fix in Phase 2 (with a test that migrates an empty DB). |

## 3. Deployment and operations

| # | Item | Why | Notes/source |
|---|---|---|---|
| FA-R27 | **Release path** (Phase 1) | Production is built on the host from a moving branch (web: D4, FA5): not reproducible, no rollback. | `tests/run.sh <image>` as nuki (`PASS:`/`FAIL:` lines, exit code, throwaway MariaDB, no secrets or network); `build_image.sh` in web_server builds release tags (`2026.1`, ...). The first release is the code running today. Production compose moves to `web: docker/compose_find_artek.yml` (FA1); `docker-compose.prod.yml` is removed here after M5 is deployed. `master` follows the deployed tag (FA5; resetting it once needs your go-ahead). |
| FA-R28 | Dev compose on the same pins | The dev stack uses floating `mariadb:11.2` and `phpmyadmin:latest`. | `compose.pins.env` here with the same digests as `web: docker/pins.env` (FA4), used by `docker-compose.yml`. |
| FA-R20 | gunicorn workers and timeout | Today: 1 sync worker, default 30 s timeout. One upload (nginx allows 300 MB on `/find/`) blocks the whole site, and a slow upload is killed at 30 s. Suggested: `--workers 2 --threads 2 --timeout 120`; `--log-level info`. | `Dockerfile.prod:105` (CMD); `web: docs/plan/PLAN_capacity-tuning.md` F7, T8; `web: nginx.conf` (`client_max_body_size 300M`). Check nginx `proxy_read_timeout` and host memory headroom. |
| FA-R21 | Pin images | `mariadb:11.2` floating, `phpmyadmin/phpmyadmin:latest` unpinned, the Python base image floats. | `docker-compose.yml:24,34`; `web: docker/pins.env` (FA4); FA-R3, FA-R28. |
| FA-R22 | Healthchecks | No `healthcheck` on any service; `restart: always` cannot detect a hung gunicorn or a DB that is up but not ready. | `HEALTHCHECK` in the image (HTTP GET on a cheap view), so `up --wait` in web: `compose_service` means healthy; mariadb `healthcheck.sh --connect --innodb_initialized` in the compose. |
| FA-R23 | Published host ports | phpMyAdmin `6001` and gunicorn `8099` are published on the host, bypassing the central nginx. | Decided in web: FA2: drop 8099, phpMyAdmin on `127.0.0.1:6001` via SSH tunnel. Lands with the move of the production compose (FA-R27). |
| FA-R24 | Prod image hygiene | The runtime image installs `sudo` with NOPASSWD for the app user (needed today only so the entrypoint can start cron), plus `nano`, `mc`, `net-tools`, `gcc`, `build-essential`, `libgdal-dev`. | `Dockerfile`; `scripts/docker-entrypoint.sh`, `docker/cron/find_artek_thumbnails`. Phase 1 (done on `agent-release-path`, T3/T4): stages, runtime 218 MB without compilers or admin tools; cron kept as monitoring_db does it (sudo-started root cron daemon, jobs as `dockeruser`, the data02 convention). Later, **cross-repo**: drop sudo (root entrypoint that drops to `dockeruser` with `gosu`) in find_artek and monitoring_db together, since both use the same pattern. |
| FA-R25 | Resource limits | No memory/CPU limits on any container. | `web: docs/plan/PLAN_capacity-tuning.md`. In the web: compose. |
| FA-R26 | Media/static on CIFS | Static and media are CIFS volumes in compose with the password in `driver_opts`; the same share is mounted on the host. | web: D9 and M5: bind mounts from the host mount instead. Understand before changing file serving (FA-R10). |

## 4. Security

| # | Item | Why | Notes/source |
|---|---|---|---|
| FA-R30 | Media access control | `media/` holds (weakly) confidential reports. nginx serves `/find/media/` without authentication, so anyone with a file URL can fetch it, including reports flagged confidential or unvalidated (the API filters those, nginx does not). Directory listings were removed 2026-11-14 in `web:`. | Serve report files only through a Django view that checks confidentiality and permission, then hands off with X-Accel-Redirect to an `internal;` nginx location (same view as FA-R10); make `/find/media/` itself internal. |
| FA-R31 | Settings structure | `DEBUG = False` hardcoded (safe), secrets from env. Weak points: no fail-fast if `SECRET_KEY` is unset; `ALLOWED_HOSTS` hardcoded with legacy hosts; `MEDIA_ROOT`/`STATIC_ROOT` hardcoded; no `CSRF_TRUSTED_ORIGINS` or HSTS. | `app-main/find_artek/settings.py`. `manage.py check --deploy`. Fail-fast for `SECRET_KEY` is natural in Phase 1 (`tests/run.sh` runs `check --deploy`). |
| FA-R32 | Credentials in notes | `readme.md` "Other notes" has LDAP snippets with a placeholder password; confirm no real credentials ever lived in git history. | `git log -S` before sharing the repo wider. |
| FA-R33 | Login stack review | CAS (`django-cas-ng`) plus LDAP (`ldap3`): confirm both are still needed and the CAS URL is current. | `settings.py`. Natural during Phase 3 (both packages must support Django 5.2). |

## 5. Quality and housekeeping

| # | Item | Why | Notes/source |
|---|---|---|---|
| FA-R40 | Tests and CI | `publications/tests.py` (882 lines) and the package `publications/tests/` (person matching) exist side by side, which breaks test discovery; `api/tests.py` and `publications_meta/tests.py` are stubs; `find_artek/test_settings.py` (SQLite) can't handle the GIS fields. Three ad-hoc scripts in `app-main/test_*.py`. No CI. | Phase 1: the suite runs (one test package per app, MariaDB). Phase 2: coverage. CI (GitHub Actions running `tests/run.sh`) as a later option. |
| FA-R44 | Coverage measurement | "Reasonable coverage" needs a number. | `coverage.py` in `requirements-dev.in`, run in the dev stack; the Phase 2 plan sets the target per app and lists the critical paths that must be covered regardless of the number. |
| FA-R41 | Leftover files | Backup/old files in the tree. | `app-main/find_artek/urls.py.bak`, `publications/utils.py.bak`, `requirements_OLD.txt`, `report.old.html`, `docker-commands.txt`, `test_files/`, `*.new` files (2026-11-16, in-progress work); `Dockerfile.develop` duplicates `Dockerfile.prod` (becomes a `dev` stage in Phase 1). |
| FA-R42 | Documentation consolidation | Several overlapping root notes; `readme.md` is a TODO list, not a README. | `readme.md`, `ENVIRONMENT_SETUP.md`, `PDF_FILENAME_NORMALIZATION.md`, `THUMBNAIL_GENERATION.md`, `app-main/IMPLEMENTATION_COMPLETE.md`, `app-main/WORKFLOW_GUIDE.md`. A real README (purpose, run, test, release, where media lives); the rest under `docs/`. The "Dependencies" and "Release" sections come with Phase 1. |
| FA-R43 | Logging and observability | Debug-level gunicorn logs; no request time in logs, no metrics. | `Dockerfile.prod:105`; `web: docs/plan/PLAN_capacity-tuning.md`. Input for FA-R11. |
