# find_artek

Django 5.2 LTS database of student reports, served at `/find/` on `arctic.sustain.dtu.dk`.
Production is deployed from the repository `dtu_sus_web_server` (playbook
`playbook_install_webapp_find_artek.yml`); planned work is in `docs/roadmap.md`. Environment
variables and the dev setup: [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md).

## Development

Everything runs in Docker (no local Python environment). From the repository root, with a
`.dev.env` (copy of `.dev.env.example`) and the dev database volume `find-artek-mariadb-dev`
(created by `docs/quick-guides/01_sync_dev_db_from_prod.md`):

```bash
DC="docker compose -f docker-compose.yml -f docker-compose.develop.yml"
$DC up -d --build      # the code is copied into the image: rebuild after changes
$DC exec -T webapp-find-artek python manage.py check --settings find_artek.development_settings
$DC exec -T webapp-find-artek python manage.py makemigrations --check --dry-run --settings find_artek.development_settings
```

- App: `http://localhost:8098/` (dev settings, no `/find` prefix). phpMyAdmin:
  `http://127.0.0.1:6002` (localhost only).
- The webapp builds the `dev` stage of the `Dockerfile`. MariaDB and phpMyAdmin run the
  images production runs, by digest (written out in `docker-compose.develop.yml`, same values
  as in `compose.pins.env`; `tests/run.sh` checks they match).

## Dockerfile and pins

One `Dockerfile` with the stages `build` (compilers, builds the venv), `runtime` (the
production image: `dockeruser` uid/gid 30000, entrypoint, cron job), `dev` (runtime plus dev
tools) and `prod` (gunicorn on `8099`, `HEALTHCHECK`). A plain `docker build .` builds the
last stage, `prod`, which is what a release ships: `prod` must stay last.

`compose.pins.env` holds the pins for deterministic builds:

| Pin | Used by |
|---|---|
| `FA_PYTHON_IMAGE` | base image; must equal `ARG PYTHON_IMAGE` in the `Dockerfile` (a release builds without `--build-arg`, so the Dockerfile default counts); `tests/run.sh` checks it |
| `FA_UV_VERSION` | `scripts/compile_lock.py` (not part of the image) |
| `FA_MARIADB_IMAGE`, `FA_PHPMYADMIN_IMAGE` | `docker-compose.develop.yml` (written out there) and the test database of `tests/run.sh`; same values as web_server's `pins.env` |

Current base image: `python:3.13.18-slim-trixie` (Debian 13; GDAL 3.10, which Django 5.2's
check `gis.W001` needs, GDAL >= 3.9), by its multi-arch index digest. To move it:

1. `docker buildx imagetools inspect python:3.13-slim-trixie`: take the exact patch tag
   (`org.opencontainers.image.version`) and the index `Digest` (the top one, not a
   per-platform manifest). Prefer an image at least two weeks old
   (`org.opencontainers.image.created`).
2. Write `python:<patch>-slim-trixie@sha256:<digest>` into both `FA_PYTHON_IMAGE`
   (`compose.pins.env`) and `ARG PYTHON_IMAGE` (`Dockerfile`).
3. Recompile the locks (`python scripts/compile_lock.py`; it reads the Python version from the
   tag, so a minor-version change needs no extra flags).
4. `docker build -t find_artek:local . && bash tests/run.sh find_artek:local`. For a new
   Debian release, check the apt package names of the `build`, `runtime` and `dev` stages too.

## Dependencies

- Direct dependencies: `app-main/requirements.in` (bounds: the version production runs up to
  the next major; Django held to its LTS series, `>=5.2.19,<5.3`), dev-only tools in
  `app-main/requirements-dev.in`.
- Locks: `app-main/requirements.txt` and `requirements-dev.txt`, generated, all transitive
  packages with hashes; never edit them by hand. The image installs with
  `pip install --require-hashes --no-deps`, and `tests/run.sh` runs `pip check`.
- Compile after editing an `.in` file. Needs Python 3.8+ and Docker on the workstation; uv
  runs in a container of the pinned Python image:

```bash
python scripts/compile_lock.py                                      # keep the locked versions, add/remove what changed
python scripts/compile_lock.py --package Django --exclude-newer 2026-11-01   # upgrade one package (repeatable)
python scripts/compile_lock.py --upgrade --exclude-newer 2026-11-01          # upgrade all (once a year)
```

Upgrades are deliberate commits; `--exclude-newer` keeps a cooldown against freshly published
versions. Rebuild and run `tests/run.sh` afterwards.

## Third-party JavaScript

The map pages use these libraries, served from our own static files
(`app-main/publications/static/publications/vendor/<lib>-<version>/`, each with its licence file),
not from a CDN:

| Library | Version | Files | Source (npm release tarball) | Licence |
|---|---|---|---|---|
| Leaflet | 1.9.4 | `leaflet.js`, `leaflet.css`, `images/` | `leaflet` | BSD-2-Clause |
| proj4js | 2.22.0 | `proj4.js` (dist build) | `proj4` | MIT |
| Proj4Leaflet | 1.0.2 | `proj4leaflet.js` (`src/`) | `proj4leaflet` | BSD-2-Clause |
| leaflet-rotate | 0.2.8 | `leaflet-rotate-src.js` | `leaflet-rotate` | GPL-3.0 |
| Leaflet.draw | 1.0.4 | `leaflet.draw.js`, `leaflet.draw.css`, `images/` | `leaflet-draw` | MIT (the tarball has no licence file; `LICENSE` written from `package.json` and the file header) |

Pages: overview map, report page, feature page (Leaflet, proj4, Proj4Leaflet, leaflet-rotate),
add feature by map (Leaflet, Leaflet.draw). Source maps (`*.map`) are not copied. The map
tiles (GBIF, later Dataforsyningen) stay external.

**Why local** (owner decision 2026-11-23): no third-party code without an integrity check runs
in editors' logged-in sessions (several of the CDN scripts were loaded without SRI); releases
are reproducible (everything that runs is in the tested image); no dependency on CDN
availability; visitors' IP addresses are not sent to CDNs; simpler security headers later
(FA-R31, Content-Security-Policy). Cost: versions are updated by hand, about 0.5 MB in the
repository.

**Updating a library** (no `npm install`, no code from the package is run):

1. Read the expected hash: `curl -s https://registry.npmjs.org/<pkg>/<version>` → `dist.integrity`
   (`sha512-...`). Prefer a version that has been out for a few weeks.
2. Download into an empty temporary directory:
   `curl -sO https://registry.npmjs.org/<pkg>/-/<pkg>-<version>.tgz`, then check
   `echo "sha512-$(openssl dgst -sha512 -binary <pkg>-<version>.tgz | base64 -w0)"` equals
   `dist.integrity`. Stop if it differs.
3. `tar -xzf <pkg>-<version>.tgz`; copy only the files in the table above and the licence file
   from `package/` into a new directory `vendor/<lib>-<version>/`; delete the old version's
   directory.
4. Change the paths in the templates (`grep -rn "publications/vendor/" app-main/publications/templates`)
   and in the table above; `test_map_assets.py` checks that every referenced file exists.
5. Raise `STATIC_ASSET_VERSION` in `settings.py`, check the map pages in the browser, run the
   tests.

## Release

- Releases are year-based tags on `develop/main`: `2026.1`, `2026.2`, fixes `2026.1.1`. A tag
  is never moved. `main` is fast-forwarded to the deployed tag afterwards.
- The image is built in `dtu_sus_web_server` (in WSL or on Linux):
  `scripts/build_image.sh webapp_find_artek <git URL or local checkout> <tag>`. It runs a plain
  `docker build` of the tag's checkout, then `bash tests/run.sh <image>`, and publishes nothing
  unless the tests pass.
  web_server's playbook deploys the built image (version in its `ansible/vars/releases.yml`)
  with its `docker/compose_find_artek.yml`. `develop/main` itself never goes live.
- Before tagging, run the image tests locally (below).

## Release notes

- **2026.6** (Phase 3, PLAN_django-5): Django 4.2.30 → 5.2.19 LTS (supported until April
  2028), Python 3.12.11 → 3.13.18 on Debian 13 trixie (GDAL 3.10: Django 5.2's `gis.W001`
  warns for GDAL < 3.9), djangorestframework 3.18.3, drf-yasg 1.21.18, django-cas-ng 5.1.2,
  django-select2 8.4.8; unused packages removed (django-taggit, psycopg, PyPDF2, python-dotenv,
  ping3). `accounts/logout/` removed (unlinked; CAS logout `/logout` is the logout); a CAS login
  link with an off-site `?next=` gives 400; the Swagger UI logout button goes to the CAS
  logout. `tests/run.sh` fails on `check --deploy` warnings other than `security.W004`/`W008`.
- **2026.2**: the appendix upload page requires login and permission to edit the report
  (FA-R52; before, anonymous users could attach files to any report). Django 4.2 → 4.2.30 (the final 4.2 patch; 4.2 LTS is end-of-life),
  djangorestframework 3.14.0 → 3.15.2 (the first version that supports Django 4.2; bound
  widened to `<3.16`). The appendix upload form uses a multi-file field (Django 4.2.1+ rejects
  `multiple` on `ClearableFileInput`, CVE-2023-31047). gunicorn runs 2 `gthread` workers × 2 threads with a 120 s timeout
  and log level `info` (was 1 sync worker, 30 s, `debug`). Production nginx needs
  `proxy_read_timeout` (and `proxy_send_timeout`) of at least 120 s on `/find/`, a change in
  dtu_sus_web_server.
- **2026.1**: the code and package versions production ran on 2026-11-16 (Django 4.2.0),
  first release built by `build_image.sh`.

## Tests

`tests/run.sh` tests a built image. From the repository root (Git Bash on Windows, WSL or Linux, with Docker):

```bash
docker build -t find_artek:local .                       # builds the last stage, prod
bash tests/run.sh find_artek:local                       # everything (~1.5 min)
bash tests/run.sh --quick find_artek:local               # image checks only, no database (~10 s)
TEST_FILTER='^smoke' bash tests/run.sh find_artek:local  # tests whose name matches (grep -E)
```

- **image:** user `dockeruser` (uid/gid 30000), `WORKDIR /app`, the entrypoint, gunicorn on `0.0.0.0:8099` without `--reload`, a `HEALTHCHECK`, `pip check`, the key packages import (GDAL, GEOS), no compilers or admin tools, the thumbnail cron file, the `Dockerfile`'s `ARG PYTHON_IMAGE` equals `FA_PYTHON_IMAGE` in `compose.pins.env` (by digest), stages `runtime`, `dev`, `prod` with `prod` last.
- **smoke:** a throwaway MariaDB on an `--internal` network with generated credentials; `migrate --skip-checks` (FA-R14), `check`, `check --deploy` (warnings reported, not failed), `makemigrations --check`, all with the production settings; the image's own command becomes healthy and answers 200 on `/publications/frontpage/`; with `ENABLE_CRON=true` the cron daemon runs and the thumbnail job, run as cron runs it, succeeds and logs to `docker logs`; no log contains the generated secrets.
- **django:** the whole Django test suite: `manage.py test` without labels (discovers every `test_*.py` module in the apps), with the production settings against the throwaway MariaDB. The `INFO:` line shows Django's `Ran <n> tests` and `OK (skipped=<k>)`. New test modules need no change in the script.

Each test prints `PASS:`/`FAIL:`; the last line is `ALL <n> TESTS PASSED` (exit 0) or `<m> OF <n> TESTS FAILED` (exit 1). All containers, the network and the temporary directory are removed at the end, also on failure. The release build (`scripts/build_image.sh` in dtu_sus_web_server) runs `bash tests/run.sh <image>` in the checkout of the release tag and publishes nothing unless it exits 0.

### Test coverage (dev stack only)

`coverage` is a dev-only package (`app-main/requirements-dev.in`, installed in the `dev` stage only; the production image doesn't contain it and `tests/run.sh` doesn't use it). The configuration is `app-main/.coveragerc` (apps `publications`, `api`, `publications_meta`, `find_artek`; migrations, test modules, `test_settings.py`, wsgi/asgi left out; branch coverage on). From the repository root, in Git Bash, with the dev stack running (rebuild after code changes):

```bash
DC="docker compose -f docker-compose.yml -f docker-compose.develop.yml"
$DC exec -T webapp-find-artek coverage run manage.py test -v 1 --noinput --buffer --settings find_artek.development_settings
$DC exec -T webapp-find-artek coverage report                    # per module, missed lines, total
$DC exec -T webapp-find-artek coverage report --include='*/publications/visibility.py'
$DC exec -T webapp-find-artek coverage html                      # writes /app/htmlcov in the container
$DC cp webapp-find-artek:/app/htmlcov ./htmlcov               # open htmlcov/index.html
```

The data file `/app/.coverage` and `htmlcov/` live in the container (gone after a rebuild); both are in `.gitignore` and `.dockerignore`.

## Roles

Every user who logs in through CAS gets the Django group `dtu_user` (set in `app-main/publications/roles.py`, at every login). The groups `artek_staff` and `artek_editor` come only from AD groups: the env variables `LDAP_GROUP_ARTEK_STAFF` and `LDAP_GROUP_ARTEK_EDITOR` hold the full DN of the AD group (nested groups count). Empty (the default) = nobody has the role. A role set by hand in the admin is removed at the user's next login; if the AD lookup fails, the current roles are kept. To give someone a role, ask DTU IT to add them to the AD group.

- `artek_staff`: add reports and delete own reports.
- `artek_editor`: add, edit, delete and verify any report, change report numbers, Excel import, edit any person and feature, delete any feature.
- Superusers (set by hand) may do everything.

What is stored about users and persons, who sees what (including confidential and unverified reports and the files under `/find/media/`): [docs/user-data-and-permissions.md](docs/user-data-and-permissions.md).

## Old TODO list

Kept for reference; planned work is tracked in `docs/roadmap.md` (items FA-R<n>).

### To do...

***URGENT***
- [x] In production, add/edit report form does not properly handle new persons not already in database (fixed on `agent-registration`, T8; not yet released)
- [] In production, add/edit report form fails during upload of pdf report. (The PDF handling was changed in T7 on `agent-registration`; retest at the 2026.3 release (FA-R12/FA-R20).)

***Not urgent***
- [] MAJOR: change to postgresql/postgis backend! (to allow handling of coordinate transformations)
- [] MAJOR: implement unit testing
- [] The add feature button is shown also when not logged in, at least in production. Check/fix
- [] remove pop-ups for user acknowledgements when separate views also ask for akcnowledgement.
       Or move popups to acknowledgement view instead of happening from report view.
- [] implement edit feature view/form
- [] check data in database against old find-artek
- [] check model setup against old find-artek
- [] clean up code (remove commented code, newlines etc) [started]


### Completed
- [x] caching causes problems when new features are added (and possibly reports added). Using context 
        variable to trigger invalidation of report feature session cache. The template then injects
        js to clear the relevant session cache key.
- [x] implement feature view
- [x] implement links to edit and delete publication        
- [x] implemented appendices upload
- [x] implemented report pdf upload
- [x] fix map view on report page (and limit features to those from the report)
- [x] fix author links, etc...
- [x] implement simple search from front page
- [x] implement individual person view
- [x] Fix null issue for person list!
- [x] implement persons api
- [x] implement persons view (list of all persons)
- [x] Ensure confidential and unvalidate entries are filtered out! (This happens in the api serializer)






### Other notes

```python
import 
ldap_server = 'ldaps://win.dtu.dk'     # Your LDAP server address
user = 'BYG-Artek_AD_Read'             # Your AD read-only username
password = 'xxxxxxxxxxxxxxxxxxx'       # Replace with your AD password
search_base = 'dc=win,dc=dtu,dc=dk'    # Base DN for your domain
```

```python
search_filter = '(&(givenName=Thomas)(sn=I*))'
```

```python
# Connect to the LDAP server
try:
    # Set up the server with secure connection and detailed logging
    server = Server(ldap_server, get_info=ALL, use_ssl=True)
    conn = Connection(server, user=user, password=password, auto_bind=True)
    # Perform the search
    conn.search(
        search_base=search_base,
        search_filter=search_filter,
        search_scope=SUBTREE,
        attributes=['*']  # Retrieve all attributes
    )
    # Process the results
    if conn.entries:
        for entry in conn.entries:
            print(entry.displayName)  # Print all details about the found entry
    else:
        print("No entries found .")
    # Unbind the connection
    conn.unbind()
except Exception as e:
    print(f"An error occurred: {e}")
```
