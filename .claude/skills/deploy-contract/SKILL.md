---
name: deploy-contract
description: What dtu_sus_web_server relies on in find_artek (port, URL prefix, paths, user, env variables, names, entrypoint/cron, tests/run.sh for build_image.sh) and how a release is made under roadmap M5 / FA1–FA5. Use when a change touches settings.py, the Dockerfile, docker-compose*.yml, scripts/, requirements, URL routing or file serving, when preparing tests/run.sh or a release, or when writing the "Deployment impact" of a plan task.
---

# The deployment contract with dtu_sus_web_server

find_artek is deployed by `C:\thin\02_Code\docker_projects\dtu_sus_web_server` (read only). Any change to an item below needs a matching change there. Flag it in the plan ("Deployment impact") and in the report. Never edit that repository yourself.

Sources there: `docs/roadmap.md` (M5, FA1–FA5, "Functional checks per service"), `docs/deploy/infrastructure.md`, `docker/services/nginx/nginx.conf` (`location /find/`), `ansible/playbook_install_webapp_find_artek.yml`, `docs/deploy/secrets.md`.

## What the deployment relies on

| Item | Here | Used there by |
|---|---|---|
| URL prefix `/find/` | `FORCE_SCRIPT_NAME = '/find'`, `STATIC_URL`, `MEDIA_URL` in `app-main/find_artek/settings.py` | nginx `location /find/` (prefix stripped), `/find/static/`, `/find/media/` |
| Container port `8099`, gunicorn `find_artek.wsgi:application` | `Dockerfile` stage `prod`, CMD | nginx upstream `webapp-find-artek:8099` |
| Container name `webapp-find-artek`, services `find-artek-mariadb-service` (container `fa-mariadb-service`) and `find-artek-phpmyadmin-service` | `docker-compose.prod.yml`, `docker-compose.yml`; `MYSQL_HOST` | nginx, the playbook, USER_STEPS commands |
| Paths `/mnt/shared-project-data/staticfiles` and `/media` | `STATIC_ROOT`, `MEDIA_ROOT`; compose volumes | the share mounted on the host, served by nginx directly |
| App user `dockeruser`, uid/gid 30000 | `Dockerfile` (stage `runtime`) | ownership of media on the share (`uid=30000` in the CIFS options) |
| Env variable names (`SECRET_KEY`, `MYSQL_*`, `LDAP_*`, `ENABLE_CRON`, `THUMBNAIL_HEIGHT`, `NETWORK_DRIVE_*`, ...) | `settings.py`, compose, `.prod.env.example` | `webapp_find_artek.env` in web_server's secrets archive |
| Entrypoint and cron (thumbnails at 02:00 when `ENABLE_CRON=true`; job `/etc/cron.d/find_artek_thumbnails` as `dockeruser`, output in `docker logs` with `[thumbnails]`) | `scripts/docker-entrypoint.sh`, `docker/cron/find_artek_thumbnails`, `scripts/generate_thumbnails_cron.sh` | functional check "cron", M5 cron post-check |
| `collectstatic` | run by `playbook_find_artek_collectstatic.yml` | static files on the share |
| Upload size up to 300 MB | views and forms; gunicorn timeout (FA-R20) | nginx `client_max_body_size 300M` |
| Live data volume `find-artek-mariadb-prod` | `docker-compose.prod.yml` | M5: `external: true` under the same name, never renamed |

Planned changes already decided there (don't fight them; align with them): the production compose moves to web_server as `docker/compose_find_artek.yml` (FA1), host port 8099 is dropped and phpMyAdmin bound to `127.0.0.1:6001` (FA2, FA-R23), `init.sql` and the fixture playbook go away (FA1, FA3), and MariaDB, phpMyAdmin and later the Python base image are pinned by digest (FA4, FA-R21).

## Releases (FA5, from M5 on)

- **Today:** the playbook clones `develop/main` and builds on the host. Every merge into `develop/main` goes live on the next deploy.
- **After M5:** releases are year-based tags on `develop/main` (`2026.1`, `2026.2`, fixes `2026.1.1`). A tag is never moved. I set tags. web_server builds the image with `scripts/build_image.sh find_artek <git URL> <tag>`, which runs `bash tests/run.sh <image>` from the tagged source and publishes nothing unless it exits 0. `master` is fast-forwarded to the deployed tag afterwards.
- The release image is built with a plain `docker build` of the repository root. The `Dockerfile` is multi-stage; the production stage `prod` must stay the last one (as in nuki). `docker-compose.prod.yml` builds `target: prod`.

## `tests/run.sh` (to be written, FA-R40 / FA5)

Interface, as in `webapp_nukissiorfiit/tests/run.sh` (read it as the reference):

- `bash tests/run.sh <image>`: the image to test as the only required argument. The exit code is 0 only if everything passed. One `PASS: <name>` or `FAIL: <name>` line per check.
- No secrets, no network, no real API: generated throwaway values for `SECRET_KEY` and the DB password, and a throwaway MariaDB container on its own network, removed at the end (also on failure).
- Planned checks (FA5): the image starts against the throwaway MariaDB; `manage.py check --deploy` and `makemigrations --check` pass; `/find/publications/frontpage/` answers 200; the Django test suite passes; dev tools are not in the production image.
- Keep it LF, `bash -n` clean, and runnable from Git Bash on the workstation and in WSL.

## Writing "Deployment impact"

For each task that touches the table above: what changes, which file in web_server must follow (nginx location, secrets entry, compose, playbook), and which rows of web_server's "Functional checks per service" prove that `/find/` still works. Put cross-repo follow-ups in the report for me. web_server tracks them in its own roadmap.
