# User steps: fix release 2026.2.1

**Done 2026-11-19:** tag `2026.2.1` = `372719be3cd4` (code as `f5e7e79`), built and tested 2026-11-19T10:31:25Z, deployed on sus-parcweb01, server checks passed (container healthy, frontpage/person/feature API 200, no database files in the image, no unverified or confidential report in the person API), `main` fast-forwarded.

`develop/main` is at `f5e7e79` (2026-11-18), on top of the release `2026.2`:

- `70cfb8d` person API lists only the reports the report API shows (no confidential; unverified only for logged-in users)
- `bedd664` feature API: the same rule for features and their reports (map pages)
- `f5e7e79` the old database copy `app-main/management/datatransfer_script/find_artek.sqlite` (personal data) removed from the repository and the image; `*.sqlite*` ignored; new image check in `tests/run.sh` (22 checks)

No migration, no new env variable, no change to the deployment contract (only new test labels and the image check in `tests/run.sh`). Same flow as 2026.2 (`docs/archive/USER_STEPS_release-path_COMPLETE.md` 5d-5h). Roadmap: FA-R73, FA-R75.

## 0. Back up the old databases (FA-R73, FA-R74)

- [ ] Copy the staging folder to the network backup share, then delete the local staging copy.

```powershell
# PowerShell; <share> = the backup share you choose, e.g. a folder next to the releases share
$src = 'C:\thin\02_Code\docker_projects\00_static_data\find_artek_db_backups'
$dst = '\\ait-pdfs\Qdrev\SUS\Groups\Arctic_backup\SUS-PArcWeb01\find_artek_db_backups'
robocopy $src $dst /E /COPY:DAT
Get-Content "$dst\MANIFEST.txt"
Get-ChildItem -Recurse -File $dst | Get-FileHash -Algorithm SHA256 | Format-Table Hash, Path -AutoSize   # = sha256 in MANIFEST.txt
# only after the hashes match:
Remove-Item -Recurse -Force $src
```

9 files, 114 MB: the 6 versions from git history (2023) and copies of the 3 files in `find_artek_OLD` (the originals there stay, FA-R74).

## 1. Tag `2026.2.1` locally

- [ ] Done

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
git log --oneline -4 develop/main                     # expect f5e7e79, or docs commits on top of it
git tag -a 2026.2.1 -m "find_artek 2026.2.1: person and feature API list no confidential/unverified reports; old database copy removed" develop/main
git show --no-patch --format='%h %s' '2026.2.1^{commit}'
```

## 2. Build and test the bundle

- [ ] Done

```bash
# WSL
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server
bash scripts/build_image.sh webapp_find_artek /mnt/c/thin/02_Code/docker_projects/find_artek_DEVELOP 2026.2.1
cat release-out/webapp_find_artek/webapp_find_artek-2026.2.1.manifest.txt
```

Expect `RESULT: OK`, 22 tests, `PASS: image: no database files under /app`, and the Django step `Ran 29 tests`. Paste the manifest (`tarball_sha256` goes into `releases.yml`).

## 3. Publish to the releases share

- [ ] Done

```powershell
# PowerShell
$dst = '\\ait-pdfs\Qdrev\SUS\Groups\Arctic_backup\SUS-PArcWeb01\releases\webapp_find_artek'
Get-ChildItem $dst                                   # must not contain webapp_find_artek-2026.2.1.* yet
Copy-Item 'C:\thin\02_Code\docker_projects\dtu_sus_web_server\release-out\webapp_find_artek\webapp_find_artek-2026.2.1.*' $dst
Get-FileHash -Algorithm SHA256 "$dst\webapp_find_artek-2026.2.1.tar.gz"   # = tarball_sha256 in the manifest
```

## 4. Deploy through web_server

- [ ] Done

In web_server: `ansible/vars/releases.yml`, `webapp_find_artek` entry: `version: "2026.2.1"`, `tarball_sha256` from step 2. Then:

```bash
# WSL, web_server with the releases.yml change committed
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server/ansible
ansible-playbook -kK -i hosts playbook_install_webapp_find_artek.yml -v --ask-vault-pass
```

Checks:

```bash
# SSH on sus-parcweb01
sudo docker ps --filter name=webapp-find-artek --format '{{.Names}}  {{.Image}}  {{.Status}}'      # webapp_find_artek:2026.2.1, healthy
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/find/publications/frontpage/          # 200
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/find/api/person/                       # 200
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/find/api/feature/                      # 200
sudo docker exec webapp-find-artek sh -c 'find /app \( -name "*.sqlite" -o -name "*.sqlite3" \) | wc -l'   # 0
# logged out, no unverified report in the person API: prints the ids of unverified reports found there (expect none)
U=$(sudo docker exec fa-mariadb-service sh -c 'MYSQL_PWD="${MARIADB_ROOT_PASSWORD:-$MYSQL_ROOT_PASSWORD}" exec mariadb -uroot -N "${MARIADB_DATABASE:-$MYSQL_DATABASE}" -e "SELECT id FROM publications_publication WHERE verified=0 OR comment LIKE \"%confidential%\""')
curl -sk https://127.0.0.1/find/api/person/ | python3 -c 'import json,sys; ids=set(int(x) for x in sys.argv[1:]); d=json.load(sys.stdin); print(sorted({p["id"] for x in d for p in x["authorships"]+x["supervisorships"]} & ids))' $U   # []
```

In the browser, logged out: the map page shows features, a person page and the person list open. Logged in: unverified reports appear again in a person's list.

Rollback: put the `2026.2` entry back in `releases.yml` and rerun the playbook (no migrations).

## 5. After the deploy

- [x] Done

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
git branch -f main 2026.2.1
```

Pushing `develop/main`, `main` and the tag to GitHub is your decision; the database file is gone from the tree after the push but still in history until the purge (FA-R77, planned next, rewrites all hashes including this tag).
