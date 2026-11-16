# 1. Copy the production database into the dev stack

**Not run yet (2026-11-16).** Remove this line when the guide has been run once.

Replace (or create) the local dev database with a copy of production's find_artek database. Modelled on dtu_sus_data02's quick-guide 4 ("Sync the dev database from a production dump").

The dump holds personal data (names, e-mail addresses, password hashes) and the confidentiality flags of reports. It stays on the workstation, outside the repository: never commit it, never copy it into tests or fixtures, and delete old dumps you no longer need.

- [1. Copy the production database into the dev stack](#1-copy-the-production-database-into-the-dev-stack)
  - [1. What runs in production](#1-what-runs-in-production)
  - [2. Dump on the host](#2-dump-on-the-host)
  - [3. Copy the dump to the workstation](#3-copy-the-dump-to-the-workstation)
  - [4. Define the dev shorthands](#4-define-the-dev-shorthands)
  - [5. Start the dev database](#5-start-the-dev-database)
  - [6. Restore](#6-restore)
  - [7. Start the app and migrate](#7-start-the-app-and-migrate)
  - [8. Check](#8-check)
  - [9. Clean up](#9-clean-up)

## 1. What runs in production

Today production is built on the host from a clone of `develop/main` (dtu_sus_web_server milestone M5 changes that):

```powershell
# PowerShell (workstation)
ssh tingeman@10.61.64.65 "sudo git -c safe.directory='*' -C /opt/webapp_find_artek log -1 --format='%h %ci %s'"
```

It prints the commit production runs (2026-11-16: `afd8792`). The dev checkout you restore into must contain all of production's migrations (step 7 checks this). After the first release, use the image tag instead: `ssh tingeman@10.61.64.65 "sudo docker ps --filter name=webapp-find-artek --format '{{.Image}}'"` prints `find_artek:<version>`.

## 2. Dump on the host

In an SSH session on `sus-parcweb01` (`ssh tingeman@10.61.64.65`). Read only for the database; the dump is a consistent snapshot (`--single-transaction`, InnoDB) and doesn't stop the site.

Check the variable names the container uses (prints names only, no values):

```bash
# SSH on sus-parcweb01
sudo docker exec fa-mariadb-service sh -c 'env | cut -d= -f1 | grep -E "^(MYSQL|MARIADB)_" | sort'
```

Expected: `MYSQL_DATABASE`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`, `MYSQL_USER` (production uses `MYSQL_*` from `.prod.env`). The commands below also accept `MARIADB_*`, in case that changes.

Row counts and character set, for the check in step 8:

```bash
# SSH on sus-parcweb01
sudo docker exec fa-mariadb-service sh -c 'DB="${MARIADB_DATABASE:-$MYSQL_DATABASE}"; MYSQL_PWD="${MARIADB_ROOT_PASSWORD:-$MYSQL_ROOT_PASSWORD}" exec mariadb -uroot -N -e "
  SELECT default_character_set_name, default_collation_name FROM information_schema.SCHEMATA WHERE schema_name = \"$DB\";
  SELECT \"publications\", COUNT(*) FROM \`$DB\`.publications_publication
  UNION ALL SELECT \"persons\",  COUNT(*) FROM \`$DB\`.publications_person
  UNION ALL SELECT \"features\", COUNT(*) FROM \`$DB\`.publications_feature
  UNION ALL SELECT \"users\",    COUNT(*) FROM \`$DB\`.auth_user
  UNION ALL SELECT \"migrations\", COUNT(*) FROM \`$DB\`.django_migrations;"'
```

Write down the output. Then the dump, into your home directory, readable only by you:

```bash
# SSH on sus-parcweb01
umask 077
F=~/find_artek_dump_$(date +%Y%m%d_%H%M).sql.gz
sudo docker exec fa-mariadb-service sh -c 'MYSQL_PWD="${MARIADB_ROOT_PASSWORD:-$MYSQL_ROOT_PASSWORD}" exec mariadb-dump -uroot --single-transaction --quick --routines --triggers --hex-blob --default-character-set=utf8mb4 "${MARIADB_DATABASE:-$MYSQL_DATABASE}"' | gzip > "$F"
ls -l "$F"; gunzip -c "$F" | tail -n 1
```

The last line must be `-- Dump completed on <date>`. The dump has no `CREATE DATABASE` (one database, without `--databases`), so it can be restored into the dev database whatever its name.

The dump goes through your home directory, not the share: the share is readable by all its users, and the dump holds password hashes and e-mail addresses. Step 3 removes it from the host.

## 3. Copy the dump to the workstation

```powershell
# PowerShell (workstation)
$DUMPS = "C:\thin\02_Code\docker_projects\00_assets\find_artek_db_dumps"   # outside every repository
New-Item -ItemType Directory -Force $DUMPS | Out-Null
scp "tingeman@10.61.64.65:find_artek_dump_*.sql.gz" $DUMPS
$DUMP = Get-ChildItem $DUMPS -Filter "find_artek_dump_*.sql.gz" | Sort-Object Name | Select-Object -Last 1
$DUMP.Name
```

Then remove it from the host:

```powershell
# PowerShell (workstation)
ssh tingeman@10.61.64.65 "rm -v ~/find_artek_dump_*.sql.gz"
```

## 4. Define the dev shorthands

Once per PowerShell session, from the root of the checkout you want to run (`find_artek_DEVELOP`, or an agent worktree such as `find_artek_agent-release-path`). Only one checkout's dev stack can run at a time (fixed container names); they all share the dev database volume.

```powershell
# PowerShell (workstation)
cd C:\thin\02_Code\docker_projects\find_artek_DEVELOP
function DC  { docker compose -f docker-compose.yml -f docker-compose.develop.yml @args }
function WEB { DC exec webapp-find-artek python manage.py @args --settings find_artek.development_settings }
function DBX { docker exec -i fa-mariadb-service-dev sh -c @args }
```

(After Phase 1 task T5, `DC` also gets `--env-file ./compose.pins.env`.)

## 5. Start the dev database

First time only: the data volume is external and must exist.

```powershell
# PowerShell (workstation)
docker volume ls --filter name=find-artek-mariadb-dev     # exists already? then skip the next line
docker volume create find-artek-mariadb-dev
```

Start only the database, and wait until it is ready:

```powershell
# PowerShell (workstation)
DC up -d find-artek-mariadb-service
docker exec fa-mariadb-service-dev healthcheck.sh --connect --innodb_initialized; $LASTEXITCODE   # 0 = ready; repeat until it is
```

On a new volume, MariaDB creates the database and user from `.dev.env` and runs `docker/mariadb-service/init.sql` (a `GRANT` to the user `mariadb`). If the container stops right away, `docker logs fa-mariadb-service-dev` shows why.

`init.sql` hard-codes the user `mariadb`, so `MYSQL_USER` in `.dev.env` must be `mariadb` (`.dev.env.example` still says `find_artek_user`). With another name MariaDB refuses the `GRANT` and the init fails. Roadmap FA-R45 makes the grant follow `$MYSQL_USER`.

If the dev database already has data you want to keep, dump it first (same command as step 2, with `docker exec fa-mariadb-service-dev`, into `$DUMPS` with the name `find_artek_dev_<date>.sql.gz`).

## 6. Restore

Stop the app, so nothing writes during the restore:

```powershell
# PowerShell (workstation)
DC stop webapp-find-artek
```

Empty the dev database, with production's character set from step 2 (default below: `utf8mb4`). **This deletes the dev data.**

```powershell
# PowerShell (workstation)
DBX 'DB="${MARIADB_DATABASE:-$MYSQL_DATABASE}"; MYSQL_PWD="${MARIADB_ROOT_PASSWORD:-$MYSQL_ROOT_PASSWORD}" exec mariadb -uroot -e "DROP DATABASE IF EXISTS \`$DB\`; CREATE DATABASE \`$DB\` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"'
```

Copy the dump into the container and load it (copying avoids piping binary data through PowerShell):

```powershell
# PowerShell (workstation)
docker cp $DUMP.FullName fa-mariadb-service-dev:/tmp/restore.sql.gz
DBX 'gunzip -c /tmp/restore.sql.gz | MYSQL_PWD="${MARIADB_ROOT_PASSWORD:-$MYSQL_ROOT_PASSWORD}" mariadb -uroot "${MARIADB_DATABASE:-$MYSQL_DATABASE}"; rc=$?; rm -f /tmp/restore.sql.gz; exit $rc'
$LASTEXITCODE    # must be 0
```

## 7. Start the app and migrate

```powershell
# PowerShell (workstation)
DC up -d --build webapp-find-artek
WEB showmigrations | Select-String "\[ \]"    # migrations of this checkout that production doesn't have
WEB migrate                                    # applies them (dev only)
WEB check
```

If `showmigrations` is fine but the app fails with a missing column or table, production has a migration this checkout doesn't: use a checkout at production's commit (step 1).

## 8. Check

Row counts equal step 2:

```powershell
# PowerShell (workstation)
DBX 'DB="${MARIADB_DATABASE:-$MYSQL_DATABASE}"; MYSQL_PWD="${MARIADB_ROOT_PASSWORD:-$MYSQL_ROOT_PASSWORD}" exec mariadb -uroot -N -e "
  SELECT \"publications\", COUNT(*) FROM \`$DB\`.publications_publication
  UNION ALL SELECT \"persons\",  COUNT(*) FROM \`$DB\`.publications_person
  UNION ALL SELECT \"features\", COUNT(*) FROM \`$DB\`.publications_feature
  UNION ALL SELECT \"users\",    COUNT(*) FROM \`$DB\`.auth_user
  UNION ALL SELECT \"migrations\", COUNT(*) FROM \`$DB\`.django_migrations;"'
```

(`migrations` can be higher than in production by the number step 7 applied.)

In the browser: http://localhost:8098/ (dev runs without the `/find` prefix) shows the front page with production's reports; a report page and the map load. PDFs and thumbnails come from `..\00_static_data\find_artek_static\media`, a local copy of the media share. That copy is older than the database (newest file 2025-08-11, checked 2026-11-16), so reports added since then show missing PDFs and thumbnails in dev. That's expected and doesn't matter for database or test work; this guide doesn't sync media (it would copy confidential reports to the workstation again).

Log in: the dev database now has production's accounts and password hashes. Try CAS first (the login link; DTU CAS may refuse `localhost` as a return address). If it doesn't work, set a local password on your own account in the dev copy (`WEB changepassword <username>`) and log in at http://localhost:8098/admin/ (Django's own login is checked before CAS).

## 9. Clean up

Keep the newest dump in `$DUMPS` if you want to restore again; delete older ones. Nothing is left on the host (step 3).
