#!/bin/bash
# Tests of the find_artek image. Run on the workstation with the docker CLI against a built
# image, from the repository root:
#
#   docker build -t find_artek:local .
#   bash tests/run.sh find_artek:local
#
# The release build (dtu_sus_web_server scripts/build_image.sh) runs the same command in the
# checkout of the release tag and writes no bundle unless it exits 0. Works under bash on
# Linux and WSL, and from Git Bash on Windows (Docker Desktop). Three groups:
#
# * image checks: the image's user is dockeruser (uid/gid 30000), WORKDIR /app, the entrypoint
#   is docker-entrypoint.sh, the command is gunicorn on 0.0.0.0:8099 (2 gthread workers x 2
#   threads, timeout 120 s) without --reload, it has a HEALTHCHECK, pip check passes, the key
#   packages import (GDAL and GEOS load), no compilers or admin tools are installed, no
#   database files (*.sqlite, *.sqlite3, *.sqlite.bak, *.db) are under /app, the
#   thumbnail cron file is root 0644 and runs as dockeruser, and the Dockerfile's ARG
#   PYTHON_IMAGE default is FA_PYTHON_IMAGE of compose.pins.env (by digest) with the stages
#   runtime, dev, prod (prod last, so a plain docker build builds it). The dev compose file
#   names the same MariaDB and
#   phpMyAdmin digests as compose.pins.env. One container (--network none) and docker image inspect.
# * smoke tests (marked slow): a throwaway MariaDB (FA_MARIADB_IMAGE of compose.pins.env) on a
#   private --internal network, with generated credentials. migrate, check, check --deploy
#   (warnings are reported, not failed), makemigrations --check, all with the production
#   settings (find_artek.settings). Then the image's own command twice: without ENABLE_CRON
#   (must become healthy, answer 200 on /publications/frontpage/ from the network, run no
#   cron) and with ENABLE_CRON=true (healthy, cron daemon running, the thumbnail job run as
#   cron runs it exits 0, reaches the DB and logs to docker logs). No log contains the
#   generated secrets.
# * Django tests (marked slow): manage.py test with the labels in DJANGO_TEST_LABELS below,
#   against the throwaway MariaDB (Django creates and drops test_find_artek). See there.
#
# Nothing leaves the workstation: the app has no network access except to the throwaway DB,
# and no real secrets are used. All containers have names starting with a unique prefix and
# are removed at the end (also on failure or Ctrl-C), together with the network and the
# temporary directory. Nothing else is touched. Each test prints "PASS: <name>" or
# "FAIL: <name>: <reason>" (a passing test may add "INFO: " lines). The last line is
# "ALL <n> TESTS PASSED" (exit 0) or "<m> OF <n> TESTS FAILED" (exit 1). Usage errors exit 2.
#
# Selecting tests, for quicker runs while working on a change:
#
#   TEST_FILTER='^image' bash tests/run.sh find_artek:local    # names matching (grep -E)
#   bash tests/run.sh --quick find_artek:local                 # skip the slow tests (no DB)
#
# TEST_FILTER is an extended regular expression matched against the test names (as printed
# after "PASS: "); only matching tests run. --quick (before or after the image) skips the
# tests marked slow. A setup runs only if a selected test needs it. Skipped tests are counted
# in a "SKIPPED: <k> test(s)" line; a selection without any test is an error (exit 2). The
# full suite (no TEST_FILTER, no --quick) is what the release build runs.
# shellcheck disable=SC2329  # test functions are called indirectly through run_test
set -euo pipefail

# Django test labels run by the release gate (manage.py test <labels>). Only tests that pass
# at the release's baseline belong here (plan PLAN_release-path A4). 2026.1 had none
# (publications/tests.py does not import; the app-main/test_*.py files are ad-hoc scripts, not
# tests); an empty list is reported as "SKIP: django: ..." and not counted. From 2026.2: the
# appendix upload form and access (FA-R52) tests. From 2026.2.1: the reports listed through the
# person API (api.test_person_api_reports) and the feature API (api.test_feature_api_reports).
# Phase 1b (registration, FA-R53/FA-R54): the role groups and their assignment at CAS login, the
# model permission methods, the login redirect under the /find prefix, the write views, the
# person data, the add/edit report form end to end (T7, FA-R55), typed new persons in it (T8, FA-R12). Phase 2 (roadmap FA-R40) adds to this list and later replaces it with the whole
# suite.
DJANGO_TEST_LABELS=(publications.test_upload_appendix_form publications.test_upload_appendix_access
                    api.test_person_api_reports api.test_feature_api_reports
                    publications.test_roles publications.test_permissions_models
                    publications.test_login_redirect publications.test_report_access
                    publications.test_write_access publications.test_person_privacy
                    publications.test_report_form publications.test_menu
                    publications.test_report_form_persons)

# Settings for all manage.py commands here: the production settings (DEBUG=False, values from
# the environment), i.e. what the release runs. LDAP_* stay unset (only used at login).
SETTINGS=find_artek.settings

usage() { echo "Usage: [TEST_FILTER=<regex>] $0 [--quick] <image>" >&2; exit 2; }
IMAGE="" QUICK=0
for a in "$@"; do
  case "$a" in
    --quick) QUICK=1 ;;
    -*) usage ;;
    *) [ -z "$IMAGE" ] || usage; IMAGE="$a" ;;
  esac
done
[ -n "$IMAGE" ] || usage
TEST_FILTER="${TEST_FILTER:-}"
# grep exits 2 on an invalid expression
rc=0; printf '' | grep -Eq -- "$TEST_FILTER" || rc=$?
[ "$rc" -le 1 ] || { echo "invalid TEST_FILTER: $TEST_FILTER" >&2; exit 2; }
command -v docker >/dev/null || { echo "docker not found" >&2; exit 2; }
docker image inspect "$IMAGE" >/dev/null 2>&1 || { echo "image not found: $IMAGE" >&2; exit 2; }

TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$TESTS_DIR/.." && pwd)"
for f in Dockerfile compose.pins.env; do
  [ -f "$REPO_DIR/$f" ] || { echo "missing $REPO_DIR/$f" >&2; exit 2; }
done
pin() { sed -n -e 's/\r$//' -e "s/^$1=//p" "$REPO_DIR/compose.pins.env"; }

# The throwaway database: the pinned MariaDB of the dev stack (= production's version, FA4)
DB_IMAGE="$(pin FA_MARIADB_IMAGE)"
[ -n "$DB_IMAGE" ] || { echo "no FA_MARIADB_IMAGE in $REPO_DIR/compose.pins.env" >&2; exit 2; }

# Git Bash: keep container paths (/app/...) as they are, and give docker Windows paths for
# host files (see hp below).
export MSYS_NO_PATHCONV=1

PFX="fa-test-$$-$RANDOM"
NET="$PFX-net"
T="$(mktemp -d "${TMPDIR:-/tmp}/fa-test.XXXXXX")"

# Host path for docker (--env-file): unchanged on Linux/WSL, C:/... form under Git Bash
hp() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s\n' "$1"; fi; }

cleanup() {
  local rc=$?
  trap - EXIT
  local ids
  ids="$(docker ps -aq --filter "name=${PFX}-" 2>/dev/null || true)"
  # shellcheck disable=SC2086  # word splitting of the id list is intended
  [ -z "$ids" ] || docker rm -f $ids >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
  [ ! -d "$T" ] || rm -rf "$T" 2>/dev/null || echo "WARNING: could not remove $T" >&2
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# Generated throwaway credentials, in env files read by the docker CLI (not on command lines)
rnd() { head -c 64 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "$1"; }
DB_PW="$(rnd 24)" SECRET="$(rnd 50)"
DB_HOST=fa-test-db   # network alias of the DB container
APP_ALIAS=webapp-find-artek   # the production container name, one of ALLOWED_HOSTS
printf '%s\n' "MARIADB_ROOT_PASSWORD=$DB_PW" "MARIADB_DATABASE=find_artek" \
  "MYSQL_ROOT_PASSWORD=$DB_PW" "MYSQL_DATABASE=find_artek" > "$T/db.env"
printf '%s\n' "SECRET_KEY=$SECRET" "MYSQL_HOST=$DB_HOST" "MYSQL_DATABASE=find_artek" \
  "MYSQL_USER=root" "MYSQL_PASSWORD=$DB_PW" > "$T/app.env"
APP_ENV=(--env-file "$(hp "$T/app.env")")

# ---- helpers -------------------------------------------------------------------------

fail_t() { echo "$*"; exit 1; }                       # fail the current test (runs in a subshell)
expect() { [ "$2" = "$3" ] || fail_t "$1: expected [$3], got [$2]"; }
contains() { case "$2" in *"$3"*) ;; *) fail_t "$1: output does not contain [$3]: $2" ;; esac; }
lacks() { case "$2" in *"$3"*) fail_t "$1: output contains [$3]: $(printf '%s\n' "$2" | grep -F -m3 -- "$3")" ;; esac; }

wait_until() {   # wait_until <tries> <cmd...>: run cmd every second until it succeeds
  local n=$1; shift
  while [ "$n" -gt 0 ]; do "$@" >/dev/null 2>&1 && return 0; sleep 1; n=$((n - 1)); done
  return 1
}

# Several checks share one container: its script runs commands with emit (EMIT), which
# prints "<key>.rc <exit code>" and "<key>.out <line>" for every line of the command's
# output. facts <group> <output> stores them in F: F[<group>.<key>.rc] is the exit code,
# F[<group>.<key>.out] the output lines. F[<group>] holds the whole output, for messages.
EMIT='emit() { k=$1; shift; o="$("$@" 2>&1)"; r=$?; echo "$k.rc $r"; [ -z "$o" ] || printf "%s\n" "$o" | sed "s/^/$k.out /"; }'
declare -A F=()
facts() {   # facts <group> <output>
  local line k v
  F[$1]="$2"
  while IFS= read -r line; do
    k="$1.${line%% *}" v="${line#* }"
    [ "$line" != "${line%% *}" ] || v=""
    case "$k" in
      *.out) F[$k]="${F[$k]:+${F[$k]}$'\n'}$v" ;;
      *) F[$k]="$v" ;;
    esac
  done <<< "$2"
}
tail_of() { printf '%s\n' "$1" | tail -n "${2:-5}"; }

PASSED=0 FAILED=0
run_test() {   # run_test <name> <function> [args...]
  local name="$1" fn="$2"; shift 2
  local out rc=0
  out="$($fn "$@" 2>&1)" || rc=$?
  if [ "$rc" -eq 0 ]; then
    PASSED=$((PASSED + 1)); echo "PASS: $name"
    printf '%s\n' "$out" | grep '^INFO: ' || true
  else
    FAILED=$((FAILED + 1)); echo "FAIL: $name: $(printf '%s' "$out" | head -n 12 | sed '2,$s/^/    /')"
  fi
}

# ---- image checks --------------------------------------------------------------------
# One container (as the image's user, --network none) collects everything; the tests check
# their part of its output (F[img.*]), or the image's configuration (docker image inspect).

img_setup() {
  facts img "$(docker run --rm --network none --name "$PFX-img" --entrypoint /bin/sh "$IMAGE" -c "$EMIT"'
    emit uid id -u
    emit gid id -g
    emit user id -un
    emit pipcheck python -m pip check
    emit imports python -c "import django, rest_framework, MySQLdb, PIL, pdf2image
from django.contrib.gis.gdal import gdal_version
from django.contrib.gis.geos import geos_version
print(django.get_version(), gdal_version().decode(), geos_version().decode())"
    emit tools sh -c "for t in gcc cc c++ make pkg-config nano mc; do command -v \$t; done; true"
    emit dbfiles find /app -xdev \( -name "*.sqlite" -o -name "*.sqlite3" -o -name "*.sqlite.bak" -o -name "*.db" \) -print
    emit cronfile stat -c "%U:%G %a" /etc/cron.d/find_artek_thumbnails
    emit cronjob grep -E "^[0-9*]" /etc/cron.d/find_artek_thumbnails
  ' 2>&1)" || true
}
need_img() { [ -n "${F[img.uid.rc]:-}" ] || fail_t "the image check container did not run: ${F[img]:-}"; }
inspect() { docker image inspect -f "$1" "$IMAGE"; }

t_user() {
  need_img
  expect "image user" "$(inspect '{{.Config.User}}')" "dockeruser"
  expect "uid of the image's user" "${F[img.uid.out]:-}" "30000"
  expect "gid of the image's user" "${F[img.gid.out]:-}" "30000"
  expect "name of the image's user" "${F[img.user.out]:-}" "dockeruser"
  expect "WORKDIR" "$(inspect '{{.Config.WorkingDir}}')" "/app"
}

t_entrypoint() {
  expect "entrypoint" "$(inspect '{{json .Config.Entrypoint}}')" '["/usr/local/bin/docker-entrypoint.sh"]'
}

t_cmd() {
  local cmd
  cmd="$(inspect '{{join .Config.Cmd " "}}')"
  contains "image command" "$cmd" "gunicorn --bind 0.0.0.0:8099 find_artek.wsgi:application"
  contains "image command" "$cmd" "--workers 2 --threads 2 --worker-class gthread --timeout 120"
  lacks "image command" "$cmd" "--reload"
}

t_healthcheck() {
  local hc
  hc="$(inspect '{{if .Config.Healthcheck}}{{join .Config.Healthcheck.Test " "}}{{end}}')"
  [ -n "$hc" ] || fail_t "the image has no HEALTHCHECK"
  contains "HEALTHCHECK" "$hc" "http://127.0.0.1:8099/"
}

t_pip_check() { need_img; expect "pip check (${F[img.pipcheck.out]:-})" "${F[img.pipcheck.rc]:-}" "0"; }
t_imports() {
  need_img
  expect "imports ($(tail_of "${F[img.imports.out]:-}" 3))" "${F[img.imports.rc]:-}" "0"
  echo "INFO: Django, GDAL, GEOS: ${F[img.imports.out]:-}"
}
t_no_dev_tools() {
  need_img
  [ -z "${F[img.tools.out]:-}" ] || fail_t "installed: $(printf '%s' "${F[img.tools.out]}" | tr '\n' ' ')"
}

t_no_db_files() {
  # Database files hold personal data (roadmap FA-R73); none may be copied into the image.
  need_img
  [ -z "${F[img.dbfiles.out]:-}" ] || fail_t "database files in the image: $(printf '%s' "${F[img.dbfiles.out]}" | tr '\n' ' ')"
}

t_cron_file() {
  need_img
  expect "owner and mode of /etc/cron.d/find_artek_thumbnails" "${F[img.cronfile.out]:-}" "root:root 644"
  [ "$(printf '%s\n' "${F[img.cronjob.out]:-}" | grep -c .)" = 1 ] || fail_t "expected one job line, got: ${F[img.cronjob.out]:-}"
  expect "user field of the job line (${F[img.cronjob.out]:-})" "$(printf '%s' "${F[img.cronjob.out]:-}" | awk '{print $6}')" "dockeruser"
}

t_pin() {
  local df pins
  df="$(sed -n -e 's/\r$//' -e 's/^ARG PYTHON_IMAGE=//p' "$REPO_DIR/Dockerfile")"
  pins="$(pin FA_PYTHON_IMAGE)"
  [ -n "$pins" ] || fail_t "no FA_PYTHON_IMAGE in compose.pins.env"
  case "$pins" in *@sha256:*) ;; *) fail_t "FA_PYTHON_IMAGE is not pinned by digest: $pins" ;; esac
  expect "Dockerfile ARG PYTHON_IMAGE vs compose.pins.env FA_PYTHON_IMAGE" "$df" "$pins"
}

# The dev stack's database and phpMyAdmin images are FA_MARIADB_IMAGE / FA_PHPMYADMIN_IMAGE
# (by digest), written out in docker-compose.develop.yml
t_dev_pins() {
  local f="$REPO_DIR/docker-compose.develop.yml" svc var want got
  [ -f "$f" ] || fail_t "missing $f"
  for svc in find-artek-mariadb-service:FA_MARIADB_IMAGE find-artek-phpmyadmin-service:FA_PHPMYADMIN_IMAGE; do
    var="${svc#*:}" svc="${svc%%:*}"
    want="$(pin "$var")"
    [ -n "$want" ] || fail_t "no $var in compose.pins.env"
    case "$want" in *@sha256:*) ;; *) fail_t "$var is not pinned by digest: $want" ;; esac
    got="$(awk -v s="  $svc:" '{ sub(/\r$/, "") } $0 == s { on = 1; next } on && /^  [^ ]/ { on = 0 } on && $1 == "image:" { print $2; exit }' "$f")"
    expect "docker-compose.develop.yml $svc image vs compose.pins.env $var" "$got" "$want"
  done
}

# runtime is built on the pinned base, dev and prod on runtime, and prod is the last stage:
# a plain docker build (build_image.sh) builds the last stage
t_stages() {
  local froms
  froms="$(sed -n -e 's/\r$//' -e 's/^FROM //p' "$REPO_DIR/Dockerfile")"
  printf '%s\n' "$froms" | grep -qx '\${PYTHON_IMAGE} AS runtime' || fail_t "no stage 'FROM \${PYTHON_IMAGE} AS runtime': $froms"
  printf '%s\n' "$froms" | grep -qx 'runtime AS dev' || fail_t "no stage 'FROM runtime AS dev': $froms"
  expect "last FROM line" "$(printf '%s\n' "$froms" | tail -n 1)" "runtime AS prod"
}

# ---- smoke tests ---------------------------------------------------------------------
# The throwaway MariaDB on a private --internal network (db), the management commands in one
# container (mgmt), and two app containers with the image's own command (app).

DB="$PFX-db"
db_setup() {
  facts db "$( (
    docker network create --internal "$NET" >/dev/null || { echo "net.out could not create $NET"; exit 0; }
    docker run -d --network "$NET" --network-alias "$DB_HOST" --name "$DB" \
      --env-file "$(hp "$T/db.env")" "$DB_IMAGE" >/dev/null || { echo "start.out could not start $DB_IMAGE"; exit 0; }
    # Ready when it accepts TCP connections (the init server of the image's entrypoint does
    # not listen on TCP). healthcheck.sh exists in newer images only.
    SECONDS=0
    if wait_until 120 docker exec "$DB" sh -c 'if command -v healthcheck.sh >/dev/null; then healthcheck.sh --connect --innodb_initialized;
        else a=$(command -v mariadb-admin || command -v mysqladmin); "$a" ping --protocol=tcp -h 127.0.0.1 -uroot -p"$MARIADB_ROOT_PASSWORD" --silent; fi'; then
      echo "ready.out $SECONDS"
    else
      echo "log.out $(docker logs "$DB" 2>&1 | tail -n 5)"
    fi
  ) 2>&1)"
}

mgmt_setup() {
  run_setup db
  [ -n "${F[db.ready.out]:-}" ] || return 0
  # The commands in order: migrate first, the others need the tables. migrate needs
  # --skip-checks (roadmap FA-R14: api/views.py queries Topic at import time, so the system
  # checks fail on an empty database).
  facts mgmt "$(docker run --rm --network "$NET" --name "$PFX-mgmt" "${APP_ENV[@]}" "$IMAGE" sh -c "$EMIT"'
    emit migrate python manage.py migrate --skip-checks --noinput --settings '"$SETTINGS"'
    emit check python manage.py check --settings '"$SETTINGS"'
    emit deploy python manage.py check --deploy --settings '"$SETTINGS"'
    emit makemig python manage.py makemigrations --check --dry-run --settings '"$SETTINGS"'
  ' 2>&1)" || true
}
need_db() { [ -n "${F[db.ready.out]:-}" ] || fail_t "the test database ($DB_IMAGE) did not start: $(tail_of "${F[db]:-}")"; }
need_mgmt() { need_db; [ -n "${F[mgmt.migrate.rc]:-}" ] || fail_t "the management container did not run: $(tail_of "${F[mgmt]:-}")"; }

t_migrate() {
  need_mgmt
  expect "migrate ($(tail_of "${F[mgmt.migrate.out]:-}"))" "${F[mgmt.migrate.rc]}" "0"
  echo "INFO: test database $DB_IMAGE ready after ${F[db.ready.out]} s"
}
t_check() { need_mgmt; expect "check ($(tail_of "${F[mgmt.check.out]:-}"))" "${F[mgmt.check.rc]:-}" "0"; }
t_check_deploy() {
  local ids
  need_mgmt
  expect "check --deploy ($(tail_of "${F[mgmt.deploy.out]:-}" 8))" "${F[mgmt.deploy.rc]:-}" "0"
  # Warnings are allowed for now (plan: errors fail, warnings are reported; roadmap FA-R31)
  ids="$(printf '%s\n' "${F[mgmt.deploy.out]:-}" | grep -oE '\([a-z_]+\.W[0-9]+\)' | tr -d '()' | sort -u | paste -sd ' ' -)"
  [ -z "$ids" ] || echo "INFO: check --deploy warnings (allowed, FA-R31): $ids"
}
t_makemigrations() {
  need_mgmt
  expect "makemigrations --check ($(tail_of "${F[mgmt.makemig.out]:-}" 8))" "${F[mgmt.makemig.rc]:-}" "0"
}

# Two app containers with the image's own command, started together: $APP without
# ENABLE_CRON (network alias webapp-find-artek, one of ALLOWED_HOSTS) and $CRON with
# ENABLE_CRON=true. Facts in F[app.*] and F[cron.*]. Both with a tty (-t), as production
# runs (tty: true in docker-compose.yml): PID 1's stdout, where the cron job writes, is then a
# pty, not a pipe.
APP="$PFX-app" CRON="$PFX-cron"
health() { docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} {{.State.Running}}' "$1"; }
CRON_CHECK='found=; for c in /proc/[0-9]*/comm; do read -r n < "$c" 2>/dev/null && [ "$n" = cron ] && found=1; done; [ -n "$found" ] && echo running || echo "not running"'

# The thumbnail job as cron runs it: the command line and PATH of the installed cron file,
# cron's minimal environment, as dockeruser (via su from root, as the cron daemon does)
RUN_JOB='cmd=$(grep -E "^[0-9*]" /etc/cron.d/find_artek_thumbnails | cut -d" " -f7-)
JOBPATH=$(sed -n "s/^PATH=//p" /etc/cron.d/find_artek_thumbnails) JOBCMD=$cmd \
  su -s /bin/sh dockeruser -c '\''exec env -i SHELL=/bin/sh PATH="$JOBPATH" HOME=/home/dockeruser LOGNAME=dockeruser /bin/sh -c "$JOBCMD"'\'''

app_setup() {
  run_setup mgmt
  [ "${F[mgmt.migrate.rc]:-}" = 0 ] || return 0
  docker run -d -t --network "$NET" --network-alias "$APP_ALIAS" --name "$APP" "${APP_ENV[@]}" "$IMAGE" >/dev/null 2>&1 || true
  docker run -d -t --network "$NET" --name "$CRON" "${APP_ENV[@]}" -e ENABLE_CRON=true -e THUMBNAIL_HEIGHT=300 "$IMAGE" >/dev/null 2>&1 || true
  SECONDS=0
  local c
  for c in "$APP" "$CRON"; do
    wait_until 150 sh -c "docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}} {{.State.Running}}' '$c' | grep -Eq '^healthy|^unhealthy|false$|^ true$'" || true
  done
  local secs=$SECONDS
  facts app "$( (
    echo "secs.out $secs"
    echo "health.out $(health "$APP" 2>&1)"
    docker exec "$APP" sh -c "$EMIT"'
      emit pid1 sh -c "tr \"\\0\" \" \" < /proc/1/cmdline"
      emit pid1uid stat -c %u /proc/1' 2>&1 || true
    docker exec "$APP" sh -c "$CRON_CHECK" 2>&1 | sed 's/^/cron.out /'
    # from another container on the network, with the production host name
    docker run --rm --network "$NET" --name "$PFX-curl" --entrypoint /bin/sh "$IMAGE" -c "$EMIT"'
      emit front curl -sS -o /tmp/body -w "%{http_code}" http://'"$APP_ALIAS"':8099/publications/frontpage/
      emit static grep -c "/find/static/" /tmp/body' 2>&1 || true
    docker logs "$APP" 2>&1 | sed 's/^/log.out /'
  ) 2>&1)"
  facts cron "$( (
    echo "health.out $(health "$CRON" 2>&1)"
    docker exec "$CRON" sh -c "$CRON_CHECK" 2>&1 | sed 's/^/daemon.out /'
    rc=0; out="$(docker exec -u root "$CRON" sh -c "$RUN_JOB" 2>&1)" || rc=$?
    echo "job.rc $rc"; [ -z "$out" ] || printf '%s\n' "$out" | sed 's/^/job.out /'
    # A second run while another one holds the lock must skip (exit 0) without working
    rc=0; out="$(docker exec "$CRON" sh -c 'exec 9>/tmp/find_artek_thumbnails.lock && flock -n 9 && generate_thumbnails_cron.sh' 2>&1)" || rc=$?
    echo "locked.rc $rc"; [ -z "$out" ] || printf '%s\n' "$out" | sed 's/^/locked.out /'
    sleep 1   # docker logs may lag a moment behind the job's last write
    docker logs "$CRON" 2>&1 | sed 's/^/log.out /'
  ) 2>&1)"
  # The generated secrets must not show up in any app log: count lines only
  facts sec "leaks.out $({ docker logs "$APP" 2>&1; docker logs "$CRON" 2>&1; } | grep -cF -e "$SECRET" -e "$DB_PW" || true)"
}
need_app() { need_mgmt; [ -n "${F[app.health.out]:-}" ] || fail_t "the app containers did not start (migrate failed?)"; }

t_app_healthy() {
  need_app
  expect "health and running after ${F[app.secs.out]:-?} s (log: $(tail_of "${F[app.log.out]:-}"))" "${F[app.health.out]}" "healthy true"
  contains "PID 1" "${F[app.pid1.out]:-}" "gunicorn --bind 0.0.0.0:8099 find_artek.wsgi:application"
  lacks "PID 1" "${F[app.pid1.out]:-}" "--reload"
  expect "uid of PID 1" "${F[app.pid1uid.out]:-}" "30000"
  expect "cron daemon without ENABLE_CRON" "${F[app.cron.out]:-}" "not running"
  contains "entrypoint log" "${F[app.log.out]:-}" "Cron disabled"
  echo "INFO: both app containers healthy after ${F[app.secs.out]} s"
}

t_frontpage() {
  need_app
  expect "GET http://$APP_ALIAS:8099/publications/frontpage/ status (${F[app.front.out]:-})" "${F[app.front.out]:-}" "200"
  [ "${F[app.static.rc]:-}" = 0 ] || fail_t "the front page has no /find/static/ URL (FORCE_SCRIPT_NAME/STATIC_URL)"
}

t_app_log() {
  need_app
  lacks "app log" "${F[app.log.out]:-}" "Traceback"
  expect "log lines with a generated secret (SECRET_KEY, DB password)" "${F[sec.leaks.out]:-}" "0"
}

t_cron_daemon() {
  need_app
  expect "health and running with ENABLE_CRON=true (log: $(tail_of "${F[cron.log.out]:-}"))" "${F[cron.health.out]:-}" "healthy true"
  expect "cron daemon with ENABLE_CRON=true" "${F[cron.daemon.out]:-}" "running"
  contains "entrypoint log" "${F[cron.log.out]:-}" "Cron enabled"
}

t_cron_job() {
  local th
  need_app
  th="$(printf '%s\n' "${F[cron.log.out]:-}" | grep -F '[thumbnails]' || true)"
  expect "exit code of the thumbnail job (${F[cron.job.out]:-}; log: $(tail_of "$th"))" "${F[cron.job.rc]:-}" "0"
  # "Processing 0 publications" comes from a query: the job had the container's DB settings
  contains "[thumbnails] lines in docker logs" "$th" "Processing 0 publications"
  contains "[thumbnails] lines in docker logs" "$th" "Thumbnail generation completed successfully"
  expect "exit code of a second run while the lock is held (${F[cron.locked.out]:-})" "${F[cron.locked.rc]:-}" "0"
  contains "second run while the lock is held" "${F[cron.locked.out]:-}" "still active, skipping"
  lacks "second run while the lock is held" "${F[cron.locked.out]:-}" "Starting thumbnail generation"
}

# ---- Django tests --------------------------------------------------------------------

t_django() {
  local out rc=0
  need_mgmt
  out="$(docker run --rm --network "$NET" --name "$PFX-django" "${APP_ENV[@]}" "$IMAGE" \
    python manage.py test -v 1 --noinput --settings "$SETTINGS" "${DJANGO_TEST_LABELS[@]}" 2>&1)" || rc=$?
  [ "$rc" -eq 0 ] || fail_t "manage.py test exit code $rc:
$(printf '%s\n' "$out" | grep -E '^(FAIL|ERROR):|^Ran |^FAILED|Error' | head -n 10)
$(tail_of "$out" 3)"
  echo "INFO: $(printf '%s\n' "$out" | grep -E '^Ran ' | tail -n 1)"
}

# ---- run -----------------------------------------------------------------------------
#   needs <setup>              the tests registered after it need <setup>_setup ("" for none)
#   add_test [--slow] <name> <function> [args...]   (--quick skips --slow tests)
#   <function> SKIP:<reason> marks a test that is reported as "SKIP: <name>: <reason>" and
#   not counted

T_NAMES=() T_CMDS=() T_NEEDS=() T_SLOW=() NEED=""
needs() { NEED="$1"; }
add_test() {
  local slow=0
  if [ "$1" = --slow ]; then slow=1; shift; fi
  T_NAMES+=("$1") T_CMDS+=("${*:2}") T_NEEDS+=("$NEED") T_SLOW+=("$slow")
}

SETUPS_DONE=" "
run_setup() {
  case "$SETUPS_DONE" in *" $1 "*) return 0 ;; esac
  SETUPS_DONE="$SETUPS_DONE$1 "
  "${1}_setup"
}

needs img
add_test "image: runs as dockeruser, uid/gid 30000, WORKDIR /app" t_user
add_test "image: pip check passes" t_pip_check
add_test "image: key packages import (django, rest_framework, MySQLdb, GDAL, GEOS, PIL, pdf2image)" t_imports
add_test "image: no compilers or dev tools (gcc, cc, c++, make, pkg-config, nano, mc)" t_no_dev_tools
add_test "image: no database files under /app (*.sqlite, *.sqlite3, *.sqlite.bak, *.db)" t_no_db_files
add_test "image: thumbnail cron job /etc/cron.d/find_artek_thumbnails is root 0644 and runs as dockeruser" t_cron_file
needs ""
add_test "image: entrypoint is /usr/local/bin/docker-entrypoint.sh" t_entrypoint
add_test "image: command is gunicorn on 0.0.0.0:8099 with find_artek.wsgi:application, without --reload" t_cmd
add_test "image: has a HEALTHCHECK on 127.0.0.1:8099" t_healthcheck
add_test "image: Dockerfile ARG PYTHON_IMAGE equals FA_PYTHON_IMAGE in compose.pins.env (digest)" t_pin
add_test "image: Dockerfile stages runtime, dev, prod, prod last" t_stages
add_test "repo: dev compose MariaDB and phpMyAdmin images equal compose.pins.env (digests)" t_dev_pins

needs mgmt
add_test --slow "smoke: migrate --skip-checks on an empty MariaDB" t_migrate
add_test --slow "smoke: manage.py check passes (production settings)" t_check
add_test --slow "smoke: manage.py check --deploy has no errors" t_check_deploy
add_test --slow "smoke: makemigrations --check reports no changes" t_makemigrations
needs app
add_test --slow "smoke: app with its own command becomes healthy (gunicorn PID 1 as uid 30000, no cron without ENABLE_CRON)" t_app_healthy
add_test --slow "smoke: GET /publications/frontpage/ from the network returns 200" t_frontpage
add_test --slow "smoke: app log has no traceback and no generated secret" t_app_log
add_test --slow "smoke: ENABLE_CRON=true: app healthy and cron daemon running" t_cron_daemon
add_test --slow "smoke: ENABLE_CRON=true: thumbnail job run as cron runs it exits 0, reaches the DB, logs to docker logs" t_cron_job
needs mgmt
if [ "${#DJANGO_TEST_LABELS[@]}" -gt 0 ]; then
  add_test --slow "django: manage.py test ${DJANGO_TEST_LABELS[*]}" t_django
else
  add_test --slow "django: tests" "SKIP:no test labels configured (Phase 2, DJANGO_TEST_LABELS in tests/run.sh)"
fi

# Selection: one grep over all names (line numbers of the matching names)
SELECTED=() SKIPPED=0
MATCHED=" $(printf '%s\n' "${T_NAMES[@]}" | grep -nE -- "$TEST_FILTER" | cut -d: -f1 | tr '\n' ' ' || true) "
for i in "${!T_NAMES[@]}"; do
  if [[ "$MATCHED" != *" $((i + 1)) "* ]] || { [ "$QUICK" -eq 1 ] && [ "${T_SLOW[i]}" -eq 1 ]; }; then
    SKIPPED=$((SKIPPED + 1))
  else
    SELECTED+=("$i")
  fi
done
[ "${#SELECTED[@]}" -gt 0 ] || { echo "no test selected (TEST_FILTER='$TEST_FILTER', quick=$QUICK)" >&2; exit 2; }

for i in "${SELECTED[@]}"; do
  case "${T_CMDS[i]}" in
    SKIP:*) echo "SKIP: ${T_NAMES[i]}: ${T_CMDS[i]#SKIP:}"; continue ;;
  esac
  [ -z "${T_NEEDS[i]}" ] || run_setup "${T_NEEDS[i]}"
  read -ra cmd <<< "${T_CMDS[i]}"   # function and arguments; the arguments have no spaces
  run_test "${T_NAMES[i]}" "${cmd[@]}"
done

[ "$SKIPPED" -eq 0 ] || echo "SKIPPED: $SKIPPED test(s) (filter/quick)"
TOTAL=$((PASSED + FAILED))
if [ "$TOTAL" -eq 0 ]; then
  echo "no test ran (only skipped ones selected)" >&2
  exit 2
fi
if [ "$FAILED" -eq 0 ]; then
  echo "ALL $TOTAL TESTS PASSED"
  exit 0
fi
echo "$FAILED OF $TOTAL TESTS FAILED"
exit 1
