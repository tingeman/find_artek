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

- [ ] Done

`master` (`v2.0.1`) is not an ancestor of `develop/main` (rebase, FA5); `git log --oneline develop/main..master` shows 26 commits, of which the roadmap found 2 with no equivalent on `develop/main`. Options: leave `master` as history for now, or (after a word with the other developer) check those 2 commits and reset your local `master` to the deployed tag (nothing pushed; pushing `master`, the tag or `develop/main` to GitHub is a separate decision):

```powershell
git log --oneline --no-merges --cherry-pick --right-only develop/main...master   # the commits only on master
# only after your decision (local only):
git branch -f master 2026.1
```

Tell the orchestrator which option you chose; it records it in the status file.
