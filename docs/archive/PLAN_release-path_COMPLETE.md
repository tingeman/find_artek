# Plan: Release path and pinning (Phase 1)

Status: **complete (2026-11-18), archived.** Releases `2026.1` (2026-11-17) and `2026.2` (2026-11-18) deployed; follow-ups in [roadmap](../roadmap.md). (Approved 2026-11-16.) Roadmap: Phase 1; FA-R27, FA-R2, FA-R3 (pin), FA-R20, FA-R21, FA-R22, FA-R24 (part), FA-R28, FA-R40 (suite runs), FA-R1 step 1. Branch: `agent-release-path` (from `develop/main`), worked in its own worktree `..\find_artek_agent-release-path`, so your uncommitted work in this checkout is untouched.

Counterpart: dtu_sus_web_server milestone **M5** (decisions FA1–FA5). That repository moves the production compose, pins MariaDB/phpMyAdmin, rewrites the playbook and deploys. This plan delivers what M5 needs from the app: a tested release image built from a tag.

## Goal

1. find_artek is built once, on the workstation, by web_server's `scripts/build_image.sh` from a release tag, tested by `tests/run.sh`, and shipped as a bundle. Nothing is built or cloned on the host any more.
2. **Release `2026.1` runs the same application code and the same Python packages as production today.** Phase 1 changes how find_artek is built and deployed, not what it does.
3. Python dependencies are hash-locked, the Python base image and the dev MariaDB/phpMyAdmin images are pinned by digest, with a documented way to upgrade them.
4. The image follows the stack's conventions (data02 and monitoring_db): one `Dockerfile` with `runtime`/`dev`/`prod` stages (prod last), user `dockeruser` uid 30000, a `HEALTHCHECK`, and cron run like monitoring_db's, so thumbnails really are generated.
5. Release `2026.2`: the last Django 4.2.x patch release and the gunicorn tuning (FA-R20), as a separate, small, reversible step.

## Current state

- Production: web: `playbook_install_webapp_find_artek.yml` clones `develop/main` and builds `Dockerfile.prod` on the host (`build: always`), using `docker-compose.yml` + `docker-compose.prod.yml` from the clone. Running commit `afd8792` (web: `docs/archive/BASELINE_nuki-path_COMPLETE.md:72`).
- `app-main/requirements.txt`: 22 packages, only `django==4.2` (= 4.2.0) and `djangorestframework==3.14.0` pinned.
- `Dockerfile.prod:1` `FROM python:3.12-slim` (floating); compilers, `sudo` NOPASSWD, `nano`, `mc` in the runtime image; `CMD` gunicorn, 1 sync worker, 30 s timeout, `--log-level debug` (`:105`). `Dockerfile.develop` is a near copy.
- Cron: `scripts/docker-entrypoint.sh` calls `setup_cron.sh` when `ENABLE_CRON=true`. `setup_cron.sh` runs `crontab -u dockeruser` and `service cron start` **without sudo, as `dockeruser`**, which can't work; and cron jobs don't see the container's env (DB credentials), so `generate_thumbnails_cron.sh` couldn't reach the database anyway. To be confirmed on the host (T0).
- Tests: `app-main/publications/tests.py` (882 lines, committed); `find_artek/test_settings.py` uses SQLite, which can't handle `MultiPointField` (`publications/models.py:577`). Whether the suite passes today is unknown. No `tests/run.sh`.
- Dev images: `mariadb:11.2`, `phpmyadmin/phpmyadmin:latest` (`docker-compose.yml:24,34`).

## Design notes

- **Reference implementations** (read only): `webapp_nukissiorfiit` for `tests/run.sh`, `scripts/compile_lock.py`, `compose.pins.env`, the three-stage `Dockerfile`; `dtu_sus_monitoring_db` for a Django image with cron (`entrypoint.sh`, `app/cron_jobs/`, the cron post-check in data02's `playbook_install_monitoring_db.yml:510-532`).
- **Pinning strategy** (roadmap FA-R2):
  - `app-main/requirements.in`: the direct dependencies, each with bounds: lower = the version production runs (T0), upper = the next major; Django held to its LTS series (`>=4.2,<4.3`). `requirements-dev.in`: dev-only tools (`-c requirements.txt`).
  - `requirements.txt` / `requirements-dev.txt`: generated, hash-locked, never edited by hand. `scripts/compile_lock.py` (from nuki) runs uv inside the pinned Python image. The first lock uses `--constraints <production pip freeze>`, so it reproduces production exactly.
  - The image installs with `pip install --require-hashes --no-deps -r requirements.txt`; the tests run `pip check`.
  - Python base image by digest in `ARG PYTHON_IMAGE` (Dockerfile) and `FA_PYTHON_IMAGE` (`compose.pins.env`), changed together, checked by `tests/run.sh`. MariaDB and phpMyAdmin by digest in `compose.pins.env`, with the same values as web: `docker/pins.env` (FA4).
  - apt packages are not version-pinned; reproducibility comes from building once and shipping the tested image (the release bundle).
  - Upgrades are deliberate commits: `compile_lock.py --package NAME` for one package (security fix), `--upgrade` once a year, both with `--exclude-newer` (cooldown). Documented in the README.
- **Cron, as monitoring_db**: keep cron in the web container, started by the entrypoint through `sudo` when `ENABLE_CRON=true` (variable name unchanged: it is in web: secrets). The job is a file in `/etc/cron.d` with user `dockeruser`. The job loads the container env (DB settings, `SECRET_KEY`, `THUMBNAIL_HEIGHT`, venv `PATH`) from `/proc/1/environ` (same uid as PID 1, mode 0400; no copy of the secrets written anywhere; decided in T4 over an env file written by the entrypoint). Its output goes to PID 1's stdout/stderr, i.e. `docker logs`, lines tagged `[thumbnails]`; there is no log file. web: M5 gets a cron post-check like data02's monitoring_db playbook (command in the T4 notes of the status file).
  - **Better option, not taken here:** no sudo in the image (root entrypoint that drops to `dockeruser` with `gosu`). That is cleaner, but monitoring_db and the data02 convention use sudo, so it's worth doing for all images together. Added to the roadmap under FA-R24 as a cross-repo item.
- **Healthcheck**: `HEALTHCHECK` in the image, `curl -fsS` against a cheap page on `127.0.0.1:8099` (nginx strips `/find`, so gunicorn sees `/publications/frontpage/`). No new view in 2026.1 (no code change). A dedicated `health/` view is a later option.
- **No application code changes in 2026.1.** Settings stay as they are; `tests/run.sh` runs `check --deploy` at the default fail level (errors fail, warnings are reported; FA-R31 deals with them later).
- **Production compose stays here until M5 is deployed**, because the current playbook still uses it. It is removed in T10.
- What web_server M5 needs from this plan (listed for that repo's plan, not done here): image name `find_artek`, tag = release version, `HEALTHCHECK` in the image (so `up --wait` means healthy), `ENABLE_CRON`/`THUMBNAIL_HEIGHT` unchanged (cron only for the exact value `true`), the cron post-check (status file, T4), the removed `setup_cron.sh` and `/var/log/find_artek/thumbnail-generation.log`, the dev pins to copy into `pins.env`, and no published ports (FA2).

## Assumptions

- A1. Python stays 3.12 in Phase 1: the exact patch production runs (T0), by digest, if it can still be pulled; otherwise the latest 3.12.x (stated in the release notes). 3.13 comes with Phase 3.
- A2. Release image name `find_artek`, version scheme as FA5 (`2026.1`, `2026.2`, fixes `2026.1.1`). You set the tags.
- A3. `develop/main` has only docs commits on top of `afd8792`, so after this plan is merged, the app code at tag `2026.1` equals production's.
- A4. The test suite is run as it is. Tests that already fail on `afd8792` are recorded in the status file, not fixed (that is Phase 2). The release gate in `tests/run.sh` runs only the tests that pass at baseline, listed explicitly; Phase 2 widens it to the full suite.
- A5. Dev ports stay (8098, 6002), bound to `127.0.0.1`. `.devcontainer` is updated to the new `dev` stage.
- A6. Resetting `master` to the first release tag (FA5) is your decision at T9; this plan doesn't touch `master`.
- A7. Your person-disambiguation work moves to its own branch (you, or I on request). When it lands, `publications/tests.py` must move into the `publications/tests/` package (they clash). Phase 2 does that if it hasn't happened.

## Tasks

### T0. Baseline on the host (you, read-only)

- Where: SSH on `sus-parcweb01`. Commands go in the status file before you run them; paste the output back.
  - `docker exec webapp-find-artek pip freeze`, `python -V`, `cat /etc/debian_version`
  - `docker image inspect --format '{{index .RepoDigests 0}}' mariadb:11.2 phpmyadmin/phpmyadmin:latest`; `docker exec fa-mariadb-service mariadb --version`
  - Cron: `docker exec -u root webapp-find-artek sh -c 'crontab -l -u dockeruser; ls /etc/cron.d; pgrep -a cron'`, `docker logs webapp-find-artek 2>&1 | grep -i -m10 -E 'cron|thumbnail'`
- Acceptance: freeze and versions saved to `docs/plan/BASELINE_release-path_COMPLETE.md`; cron state known.
- Agent: you

### T1. Worktree and test baseline

- Files: none, or `find_artek/test_settings.py` (remove if it is unusable and nothing uses it).
- Do: create the worktree and branch; bring up the dev stack from it; run `check`, `makemigrations --check` and the full suite on MariaDB; record the pass/fail list in the status file.
- Acceptance: the suite runs in the dev stack and the baseline result is recorded.
- Validation: skill `validate` 1–2.
- Agent: orchestrator (commands only), implementer if `test_settings.py` needs a decision.
- Deployment impact: none.

### T2. Hash-locked dependencies

- Files: `app-main/requirements.in`, `requirements-dev.in`, `requirements.txt`, `requirements-dev.txt` (generated), `scripts/compile_lock.py` (from nuki, adapted: `app-main/`, `FA_PYTHON_IMAGE`, `FA_UV_VERSION`), `compose.pins.env`, `app-main/requirements_OLD.txt` (removed).
- Acceptance: `compile_lock.py --constraints <T0 freeze>` produces a lock whose versions equal production's freeze for every package production has (differences listed and explained); `pip install --require-hashes` succeeds in the image.
- Validation: build the dev image; `pip check`; skill `validate` 1–2.
- Agent: implementer
- Deployment impact: none yet (the image is built by M5 from T9 onwards).

### T3. Dockerfile with stages and pinned base

- Files: `Dockerfile` (new: `runtime`, `dev`, `prod`, prod last), `Dockerfile.prod` and `Dockerfile.develop` (removed), `docker-compose.develop.yml`, `docker-compose.prod.yml` (build target, until T10), `.devcontainer/*`.
- Do: base by digest (A1); build tools only where needed to compile `mysqlclient` (a builder step or purge after install), dev tools only in `dev`; `HEALTHCHECK`; `CMD` unchanged in 2026.1 (1 worker, same flags); user, uid, paths, entrypoint, `ENABLE_CRON` unchanged.
- Acceptance: `docker build .` builds `prod`; the dev stack runs from the `dev` stage; the deployment-contract table (skill `deploy-contract`) still holds.
- Validation: skill `validate` 0–2, 4.
- Agent: implementer
- Deployment impact: build target and image name for web: M5.

### T4. Cron as monitoring_db

- Files: `scripts/docker-entrypoint.sh`, `scripts/setup_cron.sh`, `scripts/generate_thumbnails_cron.sh`, a cron file (e.g. `app-main/cron_jobs/thumbnails` or `docker/cron/`), `Dockerfile`.
- Acceptance: with `ENABLE_CRON=true`, cron runs, the job is in `/etc/cron.d` as `dockeruser`, and running the job's command by hand (as cron would, with cron's empty env) reaches the database and logs to the container log; with `false`, no cron.
- Tests: covered by `tests/run.sh` (T6).
- Validation: `bash -n`; skill `validate` 0, 3.
- Agent: implementer
- Deployment impact: web: M5 cron post-check (functional check "cron").

### T5. Pinned dev images

- Files: `compose.pins.env`, `docker-compose.yml`, `docker-compose.develop.yml`.
- Acceptance: MariaDB and phpMyAdmin by digest = production's versions (T0), same values web: `pins.env` will get; the dev stack starts with the existing dev volume; phpMyAdmin bound to `127.0.0.1`.
- Validation: skill `validate` 0.
- Agent: simple-task
- Deployment impact: the digests are handed to web: M5 (FA4).

### T6. `tests/run.sh`

- Files: `tests/run.sh`, `tests/` helpers as needed.
- Do, with nuki's interface (`bash tests/run.sh [--quick] <image>`, `TEST_FILTER`, `PASS:`/`FAIL:` lines, exit code, unique container prefix, cleanup on failure, no secrets, no network):
  - image checks: user `dockeruser` uid 30000; `CMD` gunicorn without `--reload`; `HEALTHCHECK` present; `pip check`; dev tools absent; `ARG PYTHON_IMAGE` default = `FA_PYTHON_IMAGE`; stages runtime, dev, prod with prod last.
  - smoke: a throwaway MariaDB (pinned) on an `--internal` network, dummy env with generated secrets; `migrate`; `check --deploy`; `makemigrations --check`; the image's own command becomes healthy; `/publications/frontpage/` answers 200; cron with `ENABLE_CRON=true` (T4 acceptance).
  - Django tests: the baseline-passing tests from T1 (A4), in the image, against the throwaway MariaDB.
- Acceptance: passes on the `prod` image; fails visibly when a check is broken (try one deliberately).
- Validation: `bash -n tests/run.sh`; the run itself.
- Agent: implementer
- Deployment impact: `build_image.sh` runs it on every release.

### T7. Docs and agent instructions

- Files: `readme.md` (sections Dependencies, Release, Tests; the TODO list moves to the roadmap or stays as a section), `ENVIRONMENT_SETUP.md`, `CLAUDE.md` (Commands), `.claude/skills/validate`, `.claude/skills/deploy-contract`.
- Acceptance: the commands documented are the ones that worked in T1–T6.
- Agent: simple-task (with the exact text given) or orchestrator.

### T8. Review and merge

- Fresh-context review of the whole branch (`/code-review`); fix what matters. Ask you to fast-forward `develop/main` to `agent-release-path`.
- Agent: orchestrator, then you (permission for the merge).

### T9. Release 2026.1 (you)

- Tag `2026.1` on `develop/main` (after T8). In web_server (WSL): `scripts/build_image.sh webapp_find_artek /mnt/c/thin/02_Code/docker_projects/find_artek_DEVELOP 2026.1` (local checkout, nothing pushed; name as web_server's services, changed 2026-11-17), publish the bundle, then the web: M5 plan deploys it with its functional checks. Decide on `master` (A6).
- Agent: you (deploy steps belong to web_server's M5 USER_STEPS).

### T10. Remove the production compose here (after M5 is deployed)

- Files: `docker-compose.prod.yml`, `.prod.env.example` (the variables are documented in web_server), `docker-compose.yml` (only what was prod-only), docs referring to them.
- Acceptance: nothing here describes production any more except the deployment contract; the dev stack still starts. Production secrets reach the app only from web_server's encrypted secrets archive (`webapp_find_artek.env`, FA1); this repo keeps only `*.env.example` files with the variable names. `.dev.env` stays local and git-ignored, with local-only values and no production credentials (LDAP in dev: FA-R34).
- Agent: simple-task
- Deployment impact: none (web: no longer uses them).

### T11. Release 2026.2: Django 4.2 final patch and gunicorn tuning

- Files: `requirements.in` (unchanged bounds), lock via `compile_lock.py --package django` (and `djangorestframework` within 3.14.x/3.15.x if needed for the last 4.2), `Dockerfile` `CMD` (`--workers 2 --threads 2 --worker-class gthread --timeout 120 --log-level info`, as monitoring_db), README release notes.
- Acceptance: `tests/run.sh` passes; `python -W error::DeprecationWarning manage.py check` output recorded for Phase 3; you confirm nginx `proxy_read_timeout` on `/find/` is at least 120 s (web:).
- Validation: `tests/run.sh`.
- Agent: implementer; release and deploy by you as T9.
- Deployment impact: memory per container (2 workers); web: functional check "uploads" (large file) becomes meaningful.

## Out of scope

- Test coverage beyond making the suite run (Phase 2), Django 5.2 and Python 3.13 (Phase 3), find_artek_OLD analysis and features (Phase 4).
- Settings changes (FA-R31), a health view, dropping sudo from the image (FA-R24 cross-repo), resource limits (FA-R25), media serving and access control (FA-R10, FA-R26, FA-R30).
- Everything in dtu_sus_web_server (M5 plan, compose, pins, playbook, nginx, secrets) and the person-disambiguation work.
