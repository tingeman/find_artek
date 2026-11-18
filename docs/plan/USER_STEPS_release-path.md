# User steps: Release path and pinning (Phase 1)

Plan: [PLAN_release-path.md](PLAN_release-path.md). Status: [STATUS_release-path.md](STATUS_release-path.md).

Steps only you can run (host access, decisions, merges, tags). Everything here is read-only on the host unless a step says otherwise. Paste the output of each read-only step back into the session (or into `docs/plan/BASELINE_release-path.md`), so the next tasks can use it.

### 1. Settle the open points of the dev-database guide

- [x] Done (2026-11-16)

Where: in the session. Answer P1–P7 of [`docs/quick-guides/01_sync_dev_db_from_prod.md`](../quick-guides/01_sync_dev_db_from_prod.md) (SSH user and sudo, variable names, transport, local folder, dev DB user, media, login). The orchestrator then finalises the guide.

### 2. Host baseline (T0)

- [x] Done (2026-11-16)

Where: SSH on `sus-parcweb01` (`ssh tingeman@10.61.64.65`). Read only; nothing prints a secret.

```bash
# What production runs: code, Python, Debian, packages
sudo git -c safe.directory='*' -C /opt/webapp_find_artek log -1 --format='%h %ci %s'
sudo docker inspect -f '{{.Created}}  {{.Config.Image}}' webapp-find-artek
sudo docker exec webapp-find-artek python -V
sudo docker exec webapp-find-artek cat /etc/debian_version
sudo docker exec webapp-find-artek pip freeze

# Database and phpMyAdmin images (digests for the pins, FA4 / T5)
sudo docker inspect -f '{{.Config.Image}} {{.Image}}' fa-mariadb-service fa-phpmyadmin-service
sudo docker image inspect -f '{{.RepoTags}} {{index .RepoDigests 0}}' mariadb:11.2 phpmyadmin/phpmyadmin:latest
sudo docker exec fa-mariadb-service mariadb --version

# Cron today (expected: not running, see the plan's "Current state")
sudo docker exec -u root webapp-find-artek sh -c 'crontab -l -u dockeruser; ls -l /etc/cron.d; for c in /proc/[0-9]*/comm; do read -r n < "$c" && [ "$n" = cron ] && echo "cron running"; done; true'
sudo docker logs webapp-find-artek 2>&1 | grep -i -m10 -E 'cron|thumbnail'

# Docker version (healthcheck options, compose build target)
sudo docker version --format '{{.Server.Version}}'; docker compose version
```

Expected: the commit `afd8792`; Python 3.12.x; Debian 12 or 13; about 50 packages. Paste everything back. This decides the base image (bookworm or trixie, exact patch), the first lock (T2) and the dev pins (T5).

### 3. Copy the production database into dev

- [x] Done (2026-11-16, run from the `agent-release-path` worktree; counts match production)

Where: SSH on the host and PowerShell on the workstation, as the guide says. After step 1 is settled, follow [`docs/quick-guides/01_sync_dev_db_from_prod.md`](../quick-guides/01_sync_dev_db_from_prod.md). Its step 2 can run in the same SSH session as step 2 above. Not needed for the automated checks (they use a throwaway database), but for manual testing with real data.

### 4. Release 2026.1 (T9)

T8 is merged: local `develop/main` contains `agent-release-path` (`ed3357b`) plus docs commits. Nothing is pushed: `origin/develop/main` stays at `afd8792` (production's code), so the old playbook, if anyone runs it, still builds production's code. The tag stays local and the bundle is built from the local checkout (`build_image.sh` archives the committed content at the tag with `git archive`, never the working tree, so your uncommitted files in this checkout are not in the image).

Bundle name: **`webapp_find_artek`**, not `find_artek` as in PLAN T9. It matches web_server's naming (`webapp_nuki`, playbook `playbook_install_webapp_find_artek.yml`, secrets `webapp_find_artek.env`), so `release_image` needs no name override. The name is baked into the bundle and the image tag, so M5 must use the same one.

#### 4a. Tag `2026.1` locally

- [x] Done (2026-11-17: annotated tag `2026.1` on `3d8299b`, local only)

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
git log --oneline -3 develop/main                     # expect docs commits on top of ed3357b
git tag -a 2026.1 -m "find_artek 2026.1: production code (afd8792) on the release path" develop/main
git show --no-patch --format='%h %s' '2026.1^{commit}'   # quotes needed: PowerShell reads {..} as a script block
```

#### 4b. Build and test the bundle from the local checkout

- [x] Done (2026-11-17T01:20Z: `RESULT: OK`, tests passed; manifest below)

```bash
# WSL
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server
git -C /mnt/c/thin/02_Code/docker_projects/find_artek_DEVELOP rev-parse --verify 2026.1^{commit}   # WSL git sees the tag
bash scripts/build_image.sh webapp_find_artek /mnt/c/thin/02_Code/docker_projects/find_artek_DEVELOP 2026.1
cat release-out/webapp_find_artek/webapp_find_artek-2026.1.manifest.txt
```

Use the main checkout `find_artek_DEVELOP`, not the worktree `find_artek_agent-release-path`: a worktree's `.git` file holds a Windows path that WSL git can't follow. If WSL git refuses with "dubious ownership", run `git config --global --add safe.directory /mnt/c/thin/02_Code/docker_projects/find_artek_DEVELOP` once (WSL).

Expect: last line `RESULT: OK, bundle written, tests passed` (about 1–2 min for `tests/run.sh`; its Django step shows `SKIP`, empty `DJANGO_TEST_LABELS`, A4). Manifest: `release: 2026.1`, the commit of the tag, `tests: passed ...`. Output: `webapp_find_artek-2026.1.tar.gz`, `.tar.gz.sha256`, `.manifest.txt`. **Paste the manifest here.**

Result (`release-out/webapp_find_artek/webapp_find_artek-2026.1.manifest.txt`, the tested build):

```text
release: 2026.1
image: webapp_find_artek:2026.1
git_sha: 3d8299b37764
source_ref: 2026.1
base_image: python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7
requirements_txt_sha256: 624e0b24bd04d3ded062cc2827a071891c97bb860d15fcc6ba7f5685d69af73f
tarball: webapp_find_artek-2026.1.tar.gz
tarball_sha256: 061dc954d7bb5b3229c9e075d9a4470153d32bba72ac47f2b815a52fd80fa703
image_id: sha256:0c1fc2bc01005933a1175471085637cfe697314754b15a98a9a697ea608a57d5
platform: linux/amd64
built_at: 2026-11-17T01:20:25Z
tests: passed (tests/run.sh sha256 0996d36ab74a306b16ea8ed267e35a4c2337ca44b56b57f428af66408390120d)
```

The manifest's `source:` line says `git@github.com:tingeman/find_artek.git:.` (the checkout's `origin` URL), but the build used the local checkout at the tag; `git_sha` is the tag's commit. The `releases.yml` entry for M5: `version: "2026.1"`, `tarball_sha256: "061dc954d7bb5b3229c9e075d9a4470153d32bba72ac47f2b815a52fd80fa703"`.

#### 4c. Publish the bundle to the releases share

- [x] Done (2026-11-17: three files on the share; the orchestrator hashed the tarball on the share: `061dc954…0fa703`, equal to the manifest)

```powershell
# PowerShell
$dst = '\\ait-pdfs\Qdrev\SUS\Groups\Arctic_backup\SUS-PArcWeb01\releases\webapp_find_artek'
New-Item -ItemType Directory -Force $dst | Out-Null
Get-ChildItem $dst                                   # must not contain webapp_find_artek-2026.1.* yet (never overwrite)
Copy-Item 'C:\thin\02_Code\docker_projects\dtu_sus_web_server\release-out\webapp_find_artek\webapp_find_artek-2026.1.*' $dst
Get-FileHash -Algorithm SHA256 "$dst\webapp_find_artek-2026.1.tar.gz"   # = tarball_sha256 in the manifest
```

#### 4d. Deploy through web_server M5

- [x] Done 2026-11-17 through web_server M5. The steps actually run, with their results, are in web_server `docs/archive/USER_STEPS_find-artek_COMPLETE.md` and `STATUS_find-artek_COMPLETE.md`; the commands below were the draft before M5 was planned. Still open: the `[thumbnails]` line after 02:00 UTC on 2026-11-18. The upload check is deferred to a later find_artek release.

**Blocked until web_server M5 is implemented.** web_server has no M5 plan yet: `playbook_install_webapp_find_artek.yml` still clones `develop/main` and builds on the host, there is no `docker/compose_find_artek.yml`, and `ansible/vars/releases.yml` has no `webapp_find_artek` entry. M5 (planned in web_server, not here) brings: the compose and pins (FA1, FA4), ports (FA2), FA3, `ENABLE_CRON=true` in `webapp_find_artek.env`, the `release_image` step with `release_image_service: webapp_find_artek`, and the `releases.yml` entry with `version: "2026.1"` and `tarball_sha256` from the manifest of 4b.

When M5 is merged into web_server's `develop/main`, in this order:

```bash
# 1. SSH on sus-parcweb01: database dump before the deploy (M5 step 1), into your home dir, only readable by you
umask 077
F=~/find_artek_pre_2026.1_$(date +%Y%m%d_%H%M).sql.gz
sudo docker exec fa-mariadb-service sh -c 'MYSQL_PWD="${MARIADB_ROOT_PASSWORD:-$MYSQL_ROOT_PASSWORD}" exec mariadb-dump -uroot --single-transaction --quick --routines --triggers --hex-blob --default-character-set=utf8mb4 "${MARIADB_DATABASE:-$MYSQL_DATABASE}"' | gzip > "$F"
ls -l "$F"; gunzip -c "$F" | tail -n 1               # expect "-- Dump completed on <date>"
```

```bash
# 2. WSL, web_server on develop/main with no uncommitted changes
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server/ansible
ansible-playbook -kK -i hosts playbook_install_webapp_find_artek.yml -v --ask-vault-pass
```

Expect `failed=0`, `webapp-find-artek` healthy on `webapp_find_artek:2026.1`.

```bash
# 3. SSH on sus-parcweb01: checks
sudo docker ps --filter name=webapp-find-artek --format '{{.Names}}  {{.Image}}  {{.Status}}'
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/find/publications/frontpage/      # 200
# cron post-check (T4), exit 0 = ok
sudo docker exec webapp-find-artek sh -c 'found=; for c in /proc/[0-9]*/comm; do read -r n < "$c" 2>/dev/null && [ "$n" = cron ] && found=1; done; f=/etc/cron.d/find_artek_thumbnails; [ -n "$found" ] && [ "$(stat -c %U:%a "$f")" = root:644 ] && grep -Eq "^[^#].* dockeruser /usr/local/bin/generate_thumbnails_cron.sh" "$f" && [ -r /proc/1/environ ] && [ -w /proc/1/fd/1 ] && echo "ok cron" || { echo "FAIL cron"; exit 1; }'
# next day, after 02:00 UTC
sudo docker logs webapp-find-artek 2>&1 | grep '\[thumbnails\]' | tail -n 3
```

Then the find_artek rows of "Functional checks per service" in web_server's `docs/roadmap.md` (CAS login, search, a confidential report hidden when logged out, uploads). Paste the results here. If the checks pass, fast-forward web_server `main` to the deployed commit (web_server `docs/deploy/releases.md`, "Which branch to deploy from").

Rollback: put back the previous entry in `releases.yml` (none for the first release: run the old playbook from web_server `main`); restore the dump only if the data was damaged (FA3 command in web_server's roadmap).

#### 4e. Decide on `master` (A6)

- [x] Done 2026-11-17: local `master` reset to `2026.1` (nothing pushed).

`master` (`v2.0.1`) is not an ancestor of `develop/main` (rebase, FA5); `git log --oneline develop/main..master` shows 26 commits, of which the roadmap found 2 with no equivalent on `develop/main`. Options: leave `master` as history for now, or (after a word with the other developer) check those 2 commits and reset your local `master` to the deployed tag (nothing pushed; pushing `master`, the tag or `develop/main` to GitHub is a separate decision):

```powershell
git log --oneline --no-merges --cherry-pick --right-only develop/main...master   # the commits only on master
# only after your decision (local only):
git branch -f master 2026.1
```

Tell the orchestrator which option you chose; it records it in the status file.

### 5. Release 2026.2 (T11 and FA-R52)

`develop/main` is at `8291021` (2026-11-18): T11 (Django 4.2.30, DRF 3.15.2, gunicorn 2 gthread workers × 2 threads, timeout 120 s) and FA-R52 (appendix upload requires login and edit permission). Same flow as step 4; the tag, the bundle and the share copy stay local/on the share until you decide on GitHub (step 6).

#### 5a. Thumbnail cron, first night (left over from 4d)

- [x] Done 2026-11-18: the 2026.2 container ran the job at 02:00 UTC (finished 02:00:09, `[thumbnails]` lines, no traceback): "There were 2 errors", "Thumbnail generation completed successfully". The errors are "PDF file not found" for a few publications (roadmap FA-R69).
- Earlier: **deferred 2026-11-18 until after 5g:** not run yet when checked (23:52 UTC on 2026-11-17). The 2026.2 deploy recreates the container, so check the first 02:00 UTC run of the 2026.2 container instead (same job, same `ENABLE_CRON=true`).

```bash
# SSH on sus-parcweb01, after the first 02:00 UTC following the 2026.2 deploy (5g)
sudo docker logs webapp-find-artek 2>&1 | grep '\[thumbnails\]' | tail -n 3
```

Expect lines tagged `[thumbnails]` from about 02:00 UTC with no traceback. The first run catches up on all thumbnails missing since cron stopped, so it may take a while. Nothing in the log: run the cron post-check from 4d and paste both outputs here.

#### 5b. Merge the last FA-R52 commit

- [x] Done 2026-11-18: `develop/main` fast-forwarded to `ff06b45` (merge of `develop/main` into `agent-fixes`, code = `2577e20`); dev check, makemigrations, 12/12 form + access tests, frontpage 200.

Where: in the session. `agent-fixes` has one more verified commit, `2577e20`: the release gate now also runs the 6 access tests (`publications.test_upload_appendix_access`, fixed to pass under the production settings), and the readme's 2026.2 notes name the FA-R52 fix. Say "merge" and the orchestrator fast-forwards `develop/main` to it. Tag only after that, so the 2026.2 gate tests the access check.

#### 5c. nginx timeout on `/find/` (dtu_sus_web_server)

- [x] Done (2026-11-18: web_server `062dad9`, deployed with `playbook_install_nginx.yml`, routes checked, web_server `main` fast-forwarded)

Where: dtu_sus_web_server (its own session or plan; this repo doesn't change it). T11 lets a request run up to 120 s in gunicorn, but nginx `location /find/` has no `proxy_read_timeout`, so nginx gives up after its default 60 s (the nuki and alive locations set 120 s). Add to `location /find/`:

```nginx
proxy_read_timeout 120s;
proxy_send_timeout 120s;
```

Deploy it before 2026.2, or with it. Without it 2026.2 still works; only requests between 60 and 120 s (large PDF uploads) still end in a 504.

#### 5d. Tag `2026.2` locally

- [x] Done (2026-11-18: `2026.2` → `cc410a2`, = `ff06b45` + docs)

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP, after 5b
git log --oneline -3 develop/main                     # expect ff06b45 (or a docs commit on top of it)
git tag -a 2026.2 -m "find_artek 2026.2: Django 4.2.30, DRF 3.15.2, gunicorn gthread, FA-R52 appendix upload access" develop/main
git show --no-patch --format='%h %s' '2026.2^{commit}'
```

#### 5e. Build and test the bundle

- [x] Done (2026-11-18: `RESULT: OK`, `git_sha: cc410a298e23`, `tarball_sha256: c18b90046b0ddfdda3462db07351a3a2cebb3f87d98a94cfd61d0df39548f7f0`, image `sha256:86a71267…`)

```bash
# WSL
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server
bash scripts/build_image.sh webapp_find_artek /mnt/c/thin/02_Code/docker_projects/find_artek_DEVELOP 2026.2
cat release-out/webapp_find_artek/webapp_find_artek-2026.2.manifest.txt
```

Expect `RESULT: OK, bundle written, tests passed`. Unlike 2026.1, the Django step now runs: `PASS: django: manage.py test publications.test_upload_appendix_form publications.test_upload_appendix_access`, `Ran 12 tests`; 21 tests in total. **Paste the manifest here** (`tarball_sha256` goes into `releases.yml`).

#### 5f. Publish to the releases share

- [x] Done (2026-11-18: three files on the share, sizes equal to `release-out`)

```powershell
# PowerShell
$dst = '\\ait-pdfs\Qdrev\SUS\Groups\Arctic_backup\SUS-PArcWeb01\releases\webapp_find_artek'
Get-ChildItem $dst                                   # must not contain webapp_find_artek-2026.2.* yet
Copy-Item 'C:\thin\02_Code\docker_projects\dtu_sus_web_server\release-out\webapp_find_artek\webapp_find_artek-2026.2.*' $dst
Get-FileHash -Algorithm SHA256 "$dst\webapp_find_artek-2026.2.tar.gz"   # = tarball_sha256 in the manifest
```

#### 5g. Deploy through web_server

- [x] Done (2026-11-18: web_server `f5b62ed` (`releases.yml` 2026.2), promote path with pre-deploy dump; `webapp_find_artek:2026.2` healthy, gunicorn gthread 2x2 timeout 120, frontpage 200, upload page logged out `302` (FA-R52 live; redirect to `/login` confirms FA-R67), appendix query: 175 rows without user, all 2013-2017 (FA-R68), browser checks done)

In web_server: `ansible/vars/releases.yml`, `webapp_find_artek` entry: `version: "2026.2"`, `tarball_sha256` from 5e. Then `playbook_install_webapp_find_artek.yml` (web_server `f5b62ed` on `agent-fixes`, fast-forwarded into `develop/main`). No manual dump: a new version takes the playbook's promote path, which dumps, test-restores and copies the dump off-host before any change. Checks on the host:

```bash
# SSH on sus-parcweb01
sudo docker ps --filter name=webapp-find-artek --format '{{.Names}}  {{.Image}}  {{.Status}}'   # webapp_find_artek:2026.2, healthy
sudo docker inspect -f '{{json .Config.Cmd}}' webapp-find-artek     # gunicorn ... --workers 2 --threads 2 --worker-class gthread --timeout 120
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/find/publications/frontpage/   # 200
# FA-R52: logged out, the upload page must not open (302 to the login, not 200)
curl -sk -o /dev/null -w '%{http_code} %{redirect_url}\n' https://127.0.0.1/find/publications/report/1/appendix/upload/
# Was the hole used? Appendix files created without a user (read only; a list of ids, file names, dates)
sudo docker exec fa-mariadb-service sh -c 'MYSQL_PWD="${MARIADB_ROOT_PASSWORD:-$MYSQL_ROOT_PASSWORD}" exec mariadb -uroot "${MARIADB_DATABASE:-$MYSQL_DATABASE}" -e "SELECT f.id, f.file, f.created_date, a.publication_id FROM publications_fileobject f JOIN publications_appendenciesship a ON a.fileobject_id = f.id WHERE f.created_by_id IS NULL ORDER BY f.created_date"'
```

The upload page `curl` checks two things. **302** means FA-R52 is live. The `redirect_url` shows FA-R67: if it is `https://127.0.0.1/login?next=/find/...` (no `/find` before `/login`), the login redirect leaves the app (roadmap FA-R67); paste it either way. In the browser, logged in with an editor account, open a report's "upload appendix" page: it must open. This is the first upload check, deferred from 4d. Upload a small test file only if you also remove it again afterwards.

If the SQL query returns rows from people who aren't known editors, look at those files before deleting anything. Paste all outputs here, then do the find_artek rows of web_server's "Functional checks per service".

Rollback: put the `2026.1` entry back in `releases.yml` and rerun the playbook (no migrations in 2026.2, so the database needs no restore).

#### 5h. After the deploy

- [x] Done (2026-11-18: find_artek `main` = `2026.2` (`cc410a2`), web_server `main` = `f5b62ed` (local; push both yourself, step 6))

```powershell
git branch -f main 2026.2      # local production branch follows the deployed tag (FA5)
```

### 6. GitHub and the leaked `.dev.env`

- [ ] Done

From the local remote-tracking refs (2026-11-18; the orchestrator can't reach GitHub): `origin/main` = `3d8299b` (= `2026.1`, the rename looks done), `origin/develop/main` = `a038018`, `origin/develop/author_disambiguation/refactor` = `4d77150`. Not checked: tags and `wip/disambiguation-draft` on GitHub.

1. **Rotate credentials** (decided 2026-11-18: the leaked values overlap the ones in use, so they are rotated). Details: section 6a below.
2. **Push what is left** (Git Bash, `find_artek_DEVELOP`). `develop/main` is now a plain fast-forward of `origin/develop/main`, no force needed:

```bash
git ls-remote --tags --heads origin | grep -E '2026|wip/|develop/main|main$'   # what GitHub has
git push origin develop/main                       # after 5b; it is the base of the 2026.2 tag
git push origin 2026.1 2026.2                      # after 5d
git push origin wip/disambiguation-draft           # if not there yet (your choice: it is a draft)
git push origin main                               # after 5h
```

Tell the orchestrator what you pushed; it updates the status file. web_server's docs that still say find_artek `master` (roadmap M5 "After M5", USER_TASKS 4e) need a follow-up there.

#### 6a. Rotate the leaked credentials

- [ ] Done

**What leaked:** `.dev.env` was committed in `3b721b9` (2024-12-09, 723 bytes) and `b152dad` (2024-12-10, 727 bytes). **Correction 2026-11-18:** `3b721b9` is an ancestor of `develop/main`, `origin/main`, `origin/develop/main` and the release tags (the file was deleted again the same day in `25c2e27`); `b152dad` is only in the tags `v2.0.0` and `v2.0.1`. So the first version stays in the public history even without those tags. The current `.dev.env` (534 bytes, 2025-08-07) is untracked (`.gitignore` `*.env`), but its values overlap the leaked ones (you checked, 2026-11-18). Production's values are in web_server's `docker/secrets/webapp_find_artek.env` (vault, `docs/deploy/secrets.md` there).

List which variables the leaked file had (names only, on your machine):

```bash
git show v2.0.0:.dev.env | sed 's/=.*//'; git show v2.0.1:.dev.env | sed 's/=.*//'
```

**Leaked variables** (both versions, checked 2026-11-18): `MYSQL_ROOT_USER`, `MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `SECRET_KEY`, `ROOT_SUPERUSER_NAME`, `ROOT_SUPERUSER_PASSWORD`, `ELASTIC_PASSWORD`, `ELASTIC_USERNAME`, `ELASTIC_KIBANA_ACCESS_TOKEN_NAME`, `ELASTIC_KIBANA_ACCESS_TOKEN`, plus commented-out lines `# MYSQL_ROOT_PASSWORD` and `# MYSQL_PASSWORD` (older values, also leaked). **Not leaked:** `LDAP_BIND_*`, `NETWORK_DRIVE_*`. `ROOT_SUPERUSER_*` and `ELASTIC_*` are not read by any code on `develop/main`.

**Exposure checked 2026-11-18:** the repository is public, and the leaked values are the ones in use. Reachable from outside DTU: the app at `/find/` (public; the Django admin form `/find/admin/` accepts a password because of `ModelBackend`), and `SECRET_KEY` is used by it. Not reachable: MariaDB (no published port), phpMyAdmin (`127.0.0.1:6001`, SSH tunnel only); the DTU front forwards only 80/443. **Superuser `root` (`ROOT_SUPERUSER_NAME`) does not exist in production**; users: `thin` (the only superuser and staff), `s225255`, `maljon`. So nothing exposed is urgent, provided `thin` doesn't use a leaked password (check below) and the Elastic instance is gone.

**Recommended timing:** check `thin` and Elastic now; rotate `SECRET_KEY` and the DB passwords in one maintenance window, preferably with the 2026.3 deploy (Phase 1b). The GitHub push (6.2) doesn't depend on it.

Check `thin` (Django shell on the host, one line per prompt; repeat for each leaked password, including the commented ones): `u = U.objects.get(username="thin"); print(u.has_usable_password(), u.check_password(getpass.getpass("leaked password: ")))`. `True True` = change it now (`u.set_password(getpass.getpass("new: ")); u.save()`). **Done 2026-11-18: no leaked password matches `thin`. Elastic is no longer deployed: `ELASTIC_*` need no rotation.** Left for 6a: `SECRET_KEY` and the DB passwords, with the 2026.3 deploy.

Rotate every leaked value still in use:

| Variable | Risk | How to rotate | Side effects |
|---|---|---|---|
| `SECRET_KEY` | Signs cookies, password reset links and CSRF tokens; with it someone can forge signed values | New value (generator below). Production and dev get **different** keys | All users are logged out once; open password reset links stop working |
| `ROOT_SUPERUSER_NAME` / `ROOT_SUPERUSER_PASSWORD` | A Django superuser (probably created by the old datatransfer app). If it exists in production with that password, it is a public admin login | Check in the admin (`/find/admin/`, users) whether the user exists. Then `sudo docker exec -it webapp-find-artek python manage.py changepassword <name>`, or make the password unusable if nobody needs the account | none |
| `MYSQL_PASSWORD` (app user `MYSQL_USER`), `MYSQL_ROOT_PASSWORD` | Medium: MariaDB has no published port (only the app and phpMyAdmin on `docker_default`; phpMyAdmin only through the SSH tunnel), so these need host or tunnel access | **Change the password in the running database first** (the image reads the env only on an empty data directory; the existing volume keeps its accounts), then the env file. Steps below | Between the `ALTER USER` and the redeploy, the app cannot connect (a few minutes): do it at a quiet time |
| `ELASTIC_*` | Account and API token of the old Elastic/Kibana work (branch `vicmrp/upgrade/elastic`) | If that Elastic instance still exists: revoke the token and change the password in Elastic. If it is gone: nothing to do | none for find_artek |
| older values in the commented lines | Same as above if they are still used anywhere (other apps, other databases) | Check; change where still used | – |

**LDAP bind password, in code (found 2026-11-18):** not in `.dev.env`, but hard-coded as `AUTH_LDAP_BIND_PASSWORD = "..."` for the account `cn=BYG-Artek_AD_Read,ou=Funktionskonti,ou=BYG,...` in `f0bc3ab` (2013-05-18, `find_artek/settings.py`, removed in `71b60f8` 2023-03-02) and again in `c8749a0` (2023-08-06, `app-classic/find_artek/find_artek/settings.py`, removed in `ab64506` 2023-08-22). Both commits are ancestors of `develop/main` and of every release tag (`2026.1`, `2026.2`, `v1.x`, `v2.x`), so they stay public unless the whole history is rewritten. The later file `secret/AUTH_LDAP_BIND_PASSWORD.txt` was never committed. Compare on your machine (prints the old values): `git show f0bc3ab:find_artek/settings.py | grep BIND_PASSWORD; git show c8749a0:app-classic/find_artek/find_artek/settings.py | grep BIND_PASSWORD`. If either equals the current `LDAP_BIND_PASSWORD`: have the account's password reset (DTU IT or BYG's account admin; ask which other apps use `BYG-Artek_AD_Read`), then put the new value into `webapp_find_artek.env` (vault) and rerun the playbook (the env change recreates the containers). The account reads the DTU directory (names, e-mail, groups); whether LDAPS on `win.dtu.dk` is reachable from outside DTU is not known here. **Checked 2026-11-18: neither commit holds the current password; no LDAP rotation needed.**

**`SECRET_KEY` literals in the history (searched 2026-11-18, values masked; fingerprint = first 8 hex of SHA-256 of the value):**

| Fingerprint | Length | Where (added → removed) |
|---|---|---|
| `630debb9` | 64 | `.dev.env` `3b721b9` → `25c2e27` (2024-12-09), in `main`/`develop/main` history |
| `186b37bc` | 50 | `find_artek/settings.py` `f0bc3ab` (2013) → `71b60f8` (2023-03); again `app-classic/.../settings.py` `c8749a0` → `ab64506` (2023-08) |
| `26801b58` | 66 | `find_artek/settings.py` `5e5968d` (2023-03) → `68f4e67` (2023-05) |
| `2bb80d53` | 6 | `find_artek/settings.py` `7ece330` (2023-06) → `c8749a0` (probably a placeholder) |
| `5cfbc370` | 50 | **`app/.env`** (a committed env file) `ff8cce9` (2023-08-06) → `89b4ebe` (2023-08-14) |
| `0dfef771` | 66 | `app-datatransfer/datatransfer/datatransfer/settings.py` `0d0ef9a` → `e96587c` (2023-12-26) |

The `*.env.example` values are placeholders. All commits above are in public branch history. Fingerprint the current keys on your machine and compare (prints only the fingerprint): `python3 -c "import hashlib,sys; v=[l.split('=',1)[1].split(' #')[0].strip().strip('\"\'') for l in open(sys.argv[1]) if l.startswith('SECRET_KEY=')][0]; print(hashlib.sha256(v.encode()).hexdigest()[:8])" <env file>` (production plaintext `webapp_find_artek.env`, and `.dev.env`). Also list the variable names in the committed `app/.env`: `git show ff8cce9:app/.env | sed 's/=.*//'`, and check those values like the `.dev.env` ones.

While editing the production env file anyway, drop `NETWORK_DRIVE_*` and `ENABLE_CRON` (unused by the M5 stack; web_server `docs/deploy/secrets.md`). Production has `ENABLE_CRON=False` there (checked 2026-11-18); it has no effect, because web_server's compose sets `ENABLE_CRON: "true"` under `environment:`, which wins over `env_file:`, but it misleads. **Keep `THUMBNAIL_HEIGHT=400`:** the cron wrapper reads it (`scripts/generate_thumbnails_cron.sh`); 400 is also the default, so it only documents the value. Do it in the same edit as the rotation: any change to the env file recreates all three containers at the next playbook run.

**Generating values** (WSL; `secrets` uses the OS's cryptographic random source; `token_urlsafe` gives only letters, digits, `-` and `_`, so the values are safe in a compose env file, in SQL quotes and in a shell. Don't use Django's `get_random_secret_key()` here: it contains `$`, `#` and brackets, which env files and shells can misread):

```bash
python3 - <<'EOF'
import secrets
print("SECRET_KEY=" + secrets.token_urlsafe(50))           # ~67 chars; Django wants >= 50
print("MYSQL_ROOT_PASSWORD=" + secrets.token_urlsafe(32))  # ~43 chars
print("MYSQL_PASSWORD=" + secrets.token_urlsafe(32))
EOF
```

Run it once for production and once for dev (never share a value between them). Only the command goes into the shell history, not the output; keep the terminal open until the `ALTER USER` is done, then clear it.

Generate all new values on your machine. Never paste them into a chat session.

**Production** (web_server; an agent never sees the plaintext):

1. Edit the plaintext `webapp_find_artek.env` in the outside secrets folder: new `SECRET_KEY`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` (only those whose production value was leaked); drop `NETWORK_DRIVE_*` and `ENABLE_CRON`. Then `bash scripts/vault_secrets.sh encrypt` (WSL) and commit the `.vault` file in web_server.
2. On the host, change the database passwords (interactive client, statement history off; it asks nothing, it uses the current root password from the container's env):

```bash
sudo docker exec -it -e MYSQL_HISTFILE=/dev/null fa-mariadb-service sh -c 'MYSQL_PWD="${MARIADB_ROOT_PASSWORD:-$MYSQL_ROOT_PASSWORD}" exec mariadb -uroot'
```
```sql
SELECT user, host FROM mysql.user;                       -- which accounts exist
ALTER USER '<MYSQL_USER>'@'%' IDENTIFIED BY '<new MYSQL_PASSWORD>';
ALTER USER 'root'@'%' IDENTIFIED BY '<new MYSQL_ROOT_PASSWORD>';         -- every root row the SELECT shows
ALTER USER 'root'@'localhost' IDENTIFIED BY '<new MYSQL_ROOT_PASSWORD>';
exit
```

Leave `healthcheck@...` and `mariadb.sys` alone (not from the env file). Type the passwords at the prompt; with `MYSQL_HISTFILE=/dev/null` they are not saved.

3. Right away, rerun `playbook_install_webapp_find_artek.yml` (same `releases.yml` version): it takes the converge path, and compose recreates all three containers because the env file changed (no dump on this path; a dump before step 2 is optional: web_server `docs/deploy/find_artek_admin.md`).
4. Checks on the host:

```bash
sudo docker ps --filter name=fa- --filter name=webapp-find-artek --format '{{.Names}}  {{.Status}}'   # all up, webapp healthy, all "Up" since the rerun
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/find/publications/frontpage/              # 200
sudo docker exec fa-mariadb-service sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mariadb -uroot -e "SELECT 1"'   # 1 = new root password works
```

In the browser: log in with CAS (new `SECRET_KEY`: you are logged out first), open a report, check the superuser change. phpMyAdmin through the tunnel with the new password.

Rollback: if the app cannot connect, check the `ALTER USER` rows against `SELECT user, host` (a missed host is the usual cause). Don't restore the old passwords.

**Dev** (this repository, your machine): new values in `.dev.env` (own `SECRET_KEY` and DB passwords, different from production). The dev volume `find-artek-mariadb-dev` also keeps its old accounts: run the same `ALTER USER` in the dev container (`docker compose -f docker-compose.yml -f docker-compose.develop.yml exec -e MYSQL_HISTFILE=/dev/null find-artek-mariadb-service sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mariadb -uroot'`) before editing `.dev.env`, then `$DC up -d` and open `http://localhost:8098/`.

**GitHub (optional, your decision):** delete the tags `v2.0.0` and `v2.0.1` on GitHub (`git push origin :refs/tags/v2.0.0 :refs/tags/v2.0.1`) and keep them locally, or recreate them without the file. That rewrites published history, and clones or forks may already have the file: only rotation makes the leak harmless.

Tell the orchestrator which variables were rotated (names only) and the check results.
