---
name: deploy-contract
description: What dtu_sus_web_server relies on in find_artek (port, URL prefix, paths, user, env variables, names, entrypoint/cron, tests/run.sh for build_image.sh) and how a release is made under roadmap M5 / FA1–FA5. Use when a change touches settings.py, the Dockerfile, docker-compose*.yml, scripts/, requirements, URL routing or file serving, when preparing tests/run.sh or a release, or when writing the "Deployment impact" of a plan task.
---

# The deployment contract with dtu_sus_web_server

find_artek is deployed by `C:\thin\02_Code\docker_projects\dtu_sus_web_server` (read only). Any change to an item below needs a matching change there. Flag it in the plan ("Deployment impact") and in the report. Never edit that repository yourself.

Sources there: `docker/compose_find_artek.yml` (the production stack), `ansible/playbook_install_webapp_find_artek.yml` and `ansible/tasks/find_artek_*.yml` (deploy, migrate, collectstatic, checks), `ansible/vars/releases.yml` (key `webapp_find_artek`), `docker/services/nginx/nginx.conf` (`location /find/`), `docs/deploy/secrets.md`, `docs/deploy/infrastructure.md`, `docs/roadmap.md` (M5, FA1–FA5, "Functional checks per service").

## What the deployment relies on

| Item | Here | Used there by |
|---|---|---|
| URL prefix `/find/` | `FORCE_SCRIPT_NAME = '/find'`, `STATIC_URL`, `MEDIA_URL` in `app-main/find_artek/settings.py` | nginx `location /find/` (prefix stripped), `/find/static/`, `/find/media/` |
| Container port `8099`, gunicorn `find_artek.wsgi:application` | `Dockerfile` stage `prod`, CMD | nginx upstream `webapp-find-artek:8099` |
| Container name `webapp-find-artek`, services `find-artek-mariadb-service` (container `fa-mariadb-service`) and `find-artek-phpmyadmin-service` | `docker-compose.yml` (dev); `MYSQL_HOST` | web_server's `docker/compose_find_artek.yml` (project `find_artek`), nginx, the playbook, USER_STEPS commands |
| Paths `/mnt/shared-project-data/staticfiles` and `/media` | `STATIC_ROOT`, `MEDIA_ROOT`; compose volumes | bind mounts of the host's CIFS mount in web_server's compose, served by nginx directly |
| App user `dockeruser`, uid/gid 30000 | `Dockerfile` (stage `runtime`) | ownership of static and media on the share (the host mounts it as uid/gid 30000) |
| Env variable names (`SECRET_KEY`, `MYSQL_*`, `LDAP_*`, `ENABLE_CRON`, `THUMBNAIL_HEIGHT`, ...) | `settings.py`, compose, `.dev.env.example`, the table in `ENVIRONMENT_SETUP.md` | `webapp_find_artek.env` in web_server's secrets archive; `MYSQL_HOST` and `ENABLE_CRON: "true"` set in its compose |
| Entrypoint and cron (thumbnails at 02:00 when `ENABLE_CRON=true`; job `/etc/cron.d/find_artek_thumbnails` as `dockeruser`, output in `docker logs` with `[thumbnails]`) | `scripts/docker-entrypoint.sh`, `docker/cron/find_artek_thumbnails`, `scripts/generate_thumbnails_cron.sh` | functional check "cron", M5 cron post-check |
| `migrate`, `collectstatic` | `manage.py` in the image | one-off containers of the release image run by the playbook (`ansible/tasks/find_artek_migrate.yml`) |
| Upload size up to 300 MB | views and forms; gunicorn timeout (FA-R20) | nginx `client_max_body_size 300M` |
| Live data volume `find-artek-mariadb-prod` | not here | web_server's compose, `external: true`, never renamed |

In place there since M5 (2026-11-17; don't fight it): the production compose is web_server's `docker/compose_find_artek.yml` (FA1), with no published port 8099 (nginx only) and phpMyAdmin on `127.0.0.1:6001` (SSH tunnel; FA2, FA-R23) with its own copy of `phpmyadmin-misc.ini`; no `init.sql` (FA1, FA3); MariaDB and phpMyAdmin pinned by digest in its `pins.env` (`PIN_FA_MARIADB`, `PIN_FA_PHPMYADMIN`; FA4). The Python base image is pinned here (`FA_PYTHON_IMAGE`, FA-R21).

## Releases (FA5, from M5 on)

- Releases are year-based tags on `develop/main` (`2026.1`, `2026.2`, fixes `2026.1.1`). A tag is never moved. I set tags. Only a released tag goes live; `develop/main` itself is never deployed.
- web_server builds the image with `scripts/build_image.sh webapp_find_artek <git URL or local checkout> <tag>`, which runs `bash tests/run.sh <image>` from the tagged source and publishes nothing unless it exits 0. The playbook deploys the version in `ansible/vars/releases.yml` (key `webapp_find_artek`). `main` is fast-forwarded to the deployed tag afterwards.
- The release image is built with a plain `docker build` of the repository root. The `Dockerfile` is multi-stage; the production stage `prod` must stay the last one (as in nuki).

## `tests/run.sh` (the release gate, FA5)

Interface, as in `webapp_nukissiorfiit/tests/run.sh`; `build_image.sh` runs `bash tests/run.sh <image>` with the checkout of the tag as the working directory:

- `bash tests/run.sh [--quick] <image>`, env `TEST_FILTER=<regex>`. One `PASS: <name>` or `FAIL: <name>: <reason>` line per test (`INFO:` and `SKIP:` lines are informational); last line `ALL <n> TESTS PASSED` (exit 0) or `<m> OF <n> TESTS FAILED` (exit 1); usage error exit 2.
- No secrets, no network for the app: generated throwaway `SECRET_KEY` and DB password (in env files in a temp dir), a throwaway MariaDB (`FA_MARIADB_IMAGE` of `compose.pins.env`, required: missing is a usage error, exit 2) on an `--internal` network, names prefixed `fa-test-<pid>-<random>`, everything removed at the end (also on failure or interrupt). Needs only the docker CLI and the image; the DB image is pulled if missing.
- Checks: image (user/uid 30000, WORKDIR, entrypoint, gunicorn CMD on `0.0.0.0:8099` without `--reload`, `HEALTHCHECK`, `pip check`, imports incl. GDAL, no compilers/admin tools, cron file, Dockerfile pin = `FA_PYTHON_IMAGE`, `prod` last stage); smoke with the production settings (`migrate --skip-checks` because of FA-R14, `check`, `check --deploy` errors only, `makemigrations --check`, healthy, `/publications/frontpage/` 200 via host name `webapp-find-artek`, cron with `ENABLE_CRON=true` and the job as cron runs it, no secrets in `docker logs`); Django tests: the labels in `DJANGO_TEST_LABELS` (empty in 2026.1 → `SKIP: django: ...`, Phase 2 fills it).
- Changing a contract item above (port, user, entrypoint, cron file, `ALLOWED_HOSTS` entry `webapp-find-artek`) needs the matching change in `tests/run.sh`. Keep it LF, `bash -n` clean, runnable from Git Bash and WSL.

## Writing "Deployment impact"

For each task that touches the table above: what changes, which file in web_server must follow (nginx location, secrets entry, compose, playbook), and which rows of web_server's "Functional checks per service" prove that `/find/` still works. Put cross-repo follow-ups in the report for me. web_server tracks them in its own roadmap.
