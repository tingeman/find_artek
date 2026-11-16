# Status: Release path and pinning (Phase 1)

Plan: [PLAN_release-path.md](PLAN_release-path.md). Branch: `agent-release-path` (from `develop/main`; worktree `..\find_artek_agent-release-path`, with a copy of `.dev.env`). Plan, status, user steps and roadmap live on `develop/main` (this checkout); the agent branch carries the code and the docs that describe it (README, CLAUDE.md, skills).

## Now

**Resume here** (fresh session in `find_artek_DEVELOP`: read this file and the PLAN, then `git -C ..\find_artek_agent-release-path log --oneline -8`; code work happens only in that worktree, planning docs only here).

- USER_STEPS 1–3 and the FA3 password check are done; nothing waits on you until T8.
- **In progress (2026-11-17, implementer):** A1 base image switch + T2, in the worktree, uncommitted until reviewed.
- Next for the orchestrator: base image to `python:3.12.11-slim-bookworm` by digest (A1, in T2's commit or its own), T2 (lock with `--constraints` from the baseline freeze), T5 (pins from the baseline digests), then **T7** (docs). T6 already added the readme "Tests" section and updated CLAUDE.md and the skills; what's left (README sections Dependencies and Release, `ENVIRONMENT_SETUP.md`) depends partly on T2.
- Then T8 (review, merge with your permission), T9 (release, you).

## Done

- 2026-11-16: roadmap with phases written (`docs/roadmap.md`), Phase 1 planned and approved. Decisions: phase order 1→2→3→4; release 2026.1 = production's code and packages; lock from production's `pip freeze`; cron aligned with monitoring_db (sudo kept, gosu noted as a cross-repo option under FA-R24).
- 2026-11-16: `agent-roadmap` branch and worktree deleted (superseded by `docs/roadmap.md`). Worktree for `agent-release-path` created.
- T1 2026-11-16: baseline against a throwaway MariaDB (no dev DB needed, no secrets): `check` and `makemigrations --check` pass **after** `migrate --skip-checks`; no Django test runs (see notes). Dev DB from production is still wanted for manual testing (guide).
- T3 2026-11-16: one `Dockerfile` (`build`, `runtime`, `dev`, `prod` last), base pinned by digest (`compose.pins.env` `FA_PYTHON_IMAGE`), `HEALTHCHECK` on `/publications/frontpage/` (healthy in ~9 s), CMD unchanged, compilers and admin tools only in build/dev (prod 218 MB, was ~2 GB), `.gitattributes` (LF scripts), `.dockerignore`; `pip freeze` identical to the old image; check/makemigrations pass, `check --deploy` 2 warnings (W004, W008).
- T4 2026-11-16: cron as monitoring_db: job `/etc/cron.d/find_artek_thumbnails` (from `docker/cron/`, built in, root 0644, user `dockeruser`, 02:00); entrypoint starts cron with `sudo` only for `ENABLE_CRON=true` (start failure logged, app still starts); job loads the container env from `/proc/1/environ`, output in `docker logs` tagged `[thumbnails]`; `setup_cron.sh` and the log file removed. Old setup confirmed broken in the image (`crond.pid: Permission denied`). Verified incl. a real cron run, no secrets in logs; USER_STEPS file added.
- T6 2026-11-16: `tests/run.sh` (nuki interface): 10 image checks + 9 smoke tests against a throwaway MariaDB (production settings, `migrate --skip-checks` for FA-R14, health, frontpage 200, cron job as cron runs it, no secrets in logs) + Django step with `DJANGO_TEST_LABELS` (empty → SKIP, Phase 2 fills it). 19/19 pass in ~40–55 s; fails visibly on the dev stage (7 failures); cleanup verified incl. interrupt. Test DB falls back to `mariadb:11.2` until T5 adds `FA_MARIADB_IMAGE`.
- 2026-11-16: decisions: LDAP on/off becomes a setting `USE_LDAP` (roadmap **FA-R34**, Phase 2, not in 2026.1); production secrets only from web_server's encrypted archive, this repo keeps only `*.env.example` (added to T10's acceptance); `.dev.env` stays local with no production credentials.

- T0 2026-11-16: host baseline in [BASELINE_release-path.md](BASELINE_release-path.md): `afd8792`, Python 3.12.11 on Debian 12.11 (bookworm, so the base stays bookworm, exact patch still pullable), 43 packages, `Django==4.2` (4.2.0), MariaDB 11.2.6 and phpMyAdmin digests, Docker 29.6.1 / Compose v5.2.0. Cron: **disabled** in production (`ENABLE_CRON` not `true`), so no thumbnails by cron today. Image IDs confirmed: the recorded digests are what runs.
- Decision 2026-11-16: **cron on from 2026.1**: web_server sets `ENABLE_CRON=true` in production with the M5 deploy (`.prod.env.example` already says `true`). The first night's run catches up on thumbnails missing since cron stopped. Hand-off to web_server M5 together with the cron post-check (notes below).
- USER_STEPS 1 2026-11-16: guide 01 open points settled (scp via home dir, dumps in `00_assets\find_artek_db_dumps`, dev user `mariadb`, media not synced, CAS first then local password, production uses `MYSQL_*`). `init.sql`'s hard-coded user → roadmap FA-R45.
- USER_STEPS 3 2026-11-16: dev DB restored from production (guide 01, run from the `agent-release-path` worktree): row counts match (494 publications, 930 persons, 1753 features, 3 users, 23 migrations), pages load, CAS login works on localhost. Volume `find-artek-mariadb-dev` now exists. `find_artek_DEVELOP` currently fails to build/start (`NameError: List` in your uncommitted `utils_person.py`).

- FA3 check 2026-11-17 (host, read-only): `$MARIADB_ROOT_PASSWORD` is empty in `fa-mariadb-service` (`Access denied ... using password: NO`), `$MYSQL_ROOT_PASSWORD` works (`SELECT 1` → `1`). **Hand-off to web_server:** its FA3 restore command must use `${MARIADB_ROOT_PASSWORD:-$MYSQL_ROOT_PASSWORD}` (or `MYSQL_ROOT_PASSWORD`).

## Open questions

- `master` reset to the first release tag (FA5, A6): your decision at T9.
- The prod image no longer has `mariadb-client` or admin tools (`nano`, `mc`, `ping`, ...). No known host procedure uses them inside `webapp-find-artek`; web_server M5 should confirm.

## Notes for the next session

- **Baseline findings (T1):**
  - `api/views.py:33-46` queries `Topic` at import time (Swagger description), so `check`, `migrate` and the test runner fail on an empty database: a fresh install can't be migrated without `--skip-checks`, and the API docs' topic list is frozen at process start. Not fixed in 2026.1 (no code changes); `tests/run.sh` migrates with `--skip-checks` first. Roadmap FA-R14.
  - The committed suite doesn't run: `publications/tests.py:9` imports `utils.get_all_publications`, which doesn't exist; discovery also picks up the ad-hoc `app-main/test_file_upload.py` (imports `publications.utils`, only in your uncommitted work). So the release gate in 2026.1 has **no Django tests** (A4); Phase 2 builds the suite.
  - Shell scripts are checked out with CRLF on Windows (`core.autocrlf=true`, no `.gitattributes`), so an image built from a Windows checkout has a broken entrypoint (`exec ... no such file or directory`). Production builds on Linux and is not affected; the release build runs in WSL. Fixed in T3 with `.gitattributes`.
- **For web_server M5 (T4):** cron post-check, run as the image's user, exit 0 = ok:
  `docker exec webapp-find-artek sh -c 'found=; for c in /proc/[0-9]*/comm; do read -r n < "$c" 2>/dev/null && [ "$n" = cron ] && found=1; done; f=/etc/cron.d/find_artek_thumbnails; [ -n "$found" ] && [ "$(stat -c %U:%a "$f")" = root:644 ] && grep -Eq "^[^#].* dockeruser /usr/local/bin/generate_thumbnails_cron.sh" "$f" && [ -r /proc/1/environ ] && [ -w /proc/1/fd/1 ] && echo "ok cron" || { echo "FAIL cron"; exit 1; }'`.
  Functional check: `docker logs webapp-find-artek 2>&1 | grep '\[thumbnails\]' | tail -n 3` (after 02:00 UTC), or a pass now: `docker exec webapp-find-artek generate_thumbnails_cron.sh`. Only tested on Docker Desktop; the post-check covers AppArmor on the host (`/proc/1/environ`, `/proc/1/fd/1`).
- **For web_server (T6):** the release must be built with web_server's `build_image.sh` (it allows `*.pins.env`; data02's older copy rejects every `*.env`, so `compose.pins.env` would be refused). The gate needs the docker CLI and permission to create an `--internal` network; ~1 min.
- The image resolves `django==4.2` to **4.2.0** exactly (T6 import check), same as production (T0); 2026.2 (T11) moves to the last 4.2.x.
- Base image: T3 used provisional `python:3.12.16-slim-bookworm@sha256:935c3c5b…`. T0 says production runs 3.12.11 on bookworm; per A1 switch `FA_PYTHON_IMAGE` to `python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7` (rerun `tests/run.sh`). 3.12.16 has the later security fixes; moving to it is a candidate for 2026.2.
- Phase 2 note: production settings put `MEDIA_ROOT` at `/mnt/shared-project-data/media` (not in the image); tests that write files need `override_settings(MEDIA_ROOT=<tmp>)`. Production settings log Django to `/app/debug.log`, not the console.
- Pre-existing, not fixed: `.devcontainer/devcontainer.json` and `.devcontainer/up.sh` refer to `/usr/src/venv` and `/usr/src/project`, which exist in no image (FA-R41).
- Baseline script (scratchpad, not in the repo): migrate, check, makemigrations, test against `mariadb:11.2` on an internal network with generated credentials. T6 turns this into `tests/run.sh`.
- web_server `docs/plan/USER_TASKS.md:158` still asks to merge `agent-roadmap`; it should be updated in that repo (the branch is gone, its content is in `docs/roadmap.md`).
- Your uncommitted person-disambiguation work is in the main checkout on `develop/main`. Phase 1 works in the separate worktree.
