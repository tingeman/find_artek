# Environment setup

Secrets never go into git: `.gitignore` ignores every `*.env` file except the `*.env.example`
templates and `compose.pins.env` (image pins, no secrets).

## Development

1. Copy the template and fill in your own development values (no production credentials):

   ```bash
   cp .dev.env.example .dev.env
   ```

2. Create the dev database volume `find-artek-mariadb-dev` from a production dump:
   `docs/quick-guides/01_sync_dev_db_from_prod.md`.

3. Start the dev stack from the repository root (Git Bash, WSL or Linux):

   ```bash
   DC="docker compose -f docker-compose.yml -f docker-compose.develop.yml"
   $DC up -d --build
   ```

   The app runs at `http://localhost:8098/` (settings `find_artek.development_settings`, no
   `/find` prefix), phpMyAdmin at `http://127.0.0.1:6002`. The code is copied into the image,
   so rebuild after changes. More commands: `readme.md`.

### VS Code Dev Container

With `.dev.env` in place, open the project in VS Code with the "Dev Containers" extension and
run "Dev Containers: Reopen in Container". It uses `.devcontainer/docker-compose.yml` on top of
the dev files: the source is mounted at `/workspace`, the app on port 8100, phpMyAdmin on 6002,
containers named `*-devcon`. (`.devcontainer/devcontainer.json` and `up.sh` still refer to
paths that exist in no image; roadmap FA-R41.)

## Production

Production is deployed only from the repository `dtu_sus_web_server`. Its secrets live in
web_server's encrypted secrets archive (`webapp_find_artek.env`); this repository keeps only
the dev template. Don't create a `.prod.env` here. Production runs web_server's
`docker/compose_find_artek.yml` with the release image. The table below lists the variables
web_server must provide; new variables go into it and into `.dev.env.example`, and are reported
to web_server.

## Environment variables

Read by the app (`app-main/find_artek/settings.py`):

| Variable | Meaning |
|---|---|
| `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD` | Database name and app user (the MariaDB container also creates them from these) |
| `MYSQL_HOST` | Database host; set by the compose files (here and in web_server) to `find-artek-mariadb-service` |
| `SECRET_KEY` | Django secret key (50+ random characters) |
| `LDAP_BIND_USER`, `LDAP_BIND_PASSWORD` | Read-only AD account for LDAP lookups (`ldaps://win.dtu.dk`) |

Read by the MariaDB container only: `MYSQL_ROOT_PASSWORD`.

Read by the container scripts (`scripts/docker-entrypoint.sh`, `scripts/generate_thumbnails_cron.sh`):

| Variable | Meaning |
|---|---|
| `ENABLE_CRON` | Starts the thumbnail cron job (02:00) only for the exact value `true`; dev `false`, production `true` (set by web_server's compose) |
| `THUMBNAIL_HEIGHT` | Height of generated thumbnails in pixels (default 400) |

`DEBUG` in the templates is not read: `settings.py` sets `DEBUG = False`,
`development_settings.py` sets `DEBUG = True`.
