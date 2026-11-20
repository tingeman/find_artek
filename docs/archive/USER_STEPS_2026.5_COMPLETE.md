# User steps: release 2026.5 (test coverage, PLAN_test-coverage T10 and T8)

`develop/main` is at `60bec29` (2026-11-20): T1-T9 of [PLAN_test-coverage_COMPLETE.md](PLAN_test-coverage_COMPLETE.md) plus the thumbnail fix `4f45f6d`. Gate on `a3ac558` (same code): 22/22, Django step 538 tests OK.

What changes for users:

- Report page: the thumbnail opens the report's PDF (same checked URL as the "download" link).
- Excel import (`/find/publications/add/reports_from_file/`): all or nothing. The whole file is checked first and problems are listed by sheet and row; nothing is saved if any row has a problem. Existing report numbers are skipped instead of renumbered. Column names have aliases, title may be empty, editors are optional, topics must already exist, keywords are imported, years 90-99 mean 19YY. New template with a Help sheet (the page's template link was broken before).
- Person matching from a directory (LDAP) entry no longer links unrelated persons (an existing person with empty initials or id_number matched any entry).
- Removed: `/select/persons/` (POST gave 500) and the unused `check_person_ajax` endpoint (500 on every call). Nothing in the UI links them.
- API `/find/api/report/`: a non-numeric `author_id`/`supervisor_id` gives 400 instead of 500.
- `cleanup_temp_files` only deletes old files in `media/temp/`, never database rows.

Deployment impact (web_server):

- No migration. Requirements (production lock) unchanged; the Dockerfile change is a comment in the `dev` stage.
- New optional env variable `USE_LDAP` (true/false; unset or empty = true, an invalid value stops startup). Nothing to add to `webapp_find_artek.env` unless LDAP should be switched off.
- `tests/run.sh` runs the whole Django suite: `build_image.sh` takes about 1.5 min longer; interface unchanged.

## 0. Fast-forward `develop/main` (main session, with your OK)

- [x] Done (2026-11-20, main session): `develop/main` fast-forwarded to `60bec29`.

## 1. Tag `2026.5` locally

- [x] Done (2026-11-20, main session, with your OK): annotated tag on `60bec29`.

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
git show --no-patch --format='%h %s' '2026.5^{commit}'     # 60bec29
```

The tag is local. Push it when you push `develop/main`: `git push origin develop/main 2026.5`.

## 2. Build and test the bundle

- [x] Done (2026-11-20, main session): `RESULT: OK, bundle written, tests passed`, 22/22, `Ran 538 tests` OK; tarball_sha256 `bdf17edcf8c12e0dc5a327aa2c106f5ee3cd1d8b8c689fa6aa5214f577bdbf46`, image_id `sha256:c4648ed13662...`, built 2026-11-20T20:30:18Z, git_sha `60bec2976109`.

```bash
# WSL
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server
bash scripts/build_image.sh webapp_find_artek /mnt/c/thin/02_Code/docker_projects/find_artek_DEVELOP 2026.5
cat release-out/webapp_find_artek/webapp_find_artek-2026.5.manifest.txt
```

## 3. Publish to the releases share

- [x] Done (2026-11-20, main session): tarball, `.sha256` and manifest copied; hash on the share matches the manifest.

```powershell
# PowerShell
$dst = '\\ait-pdfs\Qdrev\SUS\Groups\Arctic_backup\SUS-PArcWeb01\releases\webapp_find_artek'
Get-ChildItem $dst                                   # must not contain webapp_find_artek-2026.5.* yet
Copy-Item 'C:\thin\02_Code\docker_projects\dtu_sus_web_server\release-out\webapp_find_artek\webapp_find_artek-2026.5.*' $dst
Get-FileHash -Algorithm SHA256 "$dst\webapp_find_artek-2026.5.tar.gz"   # = tarball_sha256 in the manifest
```

## 4. releases.yml (web_server)

- [x] Done (2026-11-20, main session, with your OK): `version: "2026.5"`, `tarball_sha256` from the manifest, 2026.4 kept commented out for rollback; committed on web_server `develop/main` (`6b0304d`, not pushed).

## 5. Deploy the app (you)

- [x] Done (2026-11-20): `webapp_find_artek:2026.5` healthy, frontpage 200, migrations unchanged (`0004`), no traceback or error in the log.

```bash
# WSL
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server/ansible
ansible-playbook -kK -i hosts playbook_install_webapp_find_artek.yml -v --ask-vault-pass
```

`migrate --plan` should show no migrations.

Server checks:

```bash
# SSH on sus-parcweb01
sudo docker ps --filter name=webapp-find-artek --format '{{.Names}}  {{.Image}}  {{.Status}}'      # webapp_find_artek:2026.5, healthy
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/find/publications/frontpage/          # 200
sudo docker exec webapp-find-artek python manage.py showmigrations publications | tail -1          # [X] 0004_publication_confidential (unchanged)
sudo docker logs --since 10m webapp-find-artek 2>&1 | grep -iE 'traceback|error' | head            # nothing
```

Rollback: put the `2026.4` entry back in `releases.yml` (commented out above the 2026.5 entry) and rerun the playbook. No migration to reverse.

## 6. Functional checks in the browser (you)

- [x] Done (2026-11-20): all browser checks pass. Found: a deleted report still shows in the report list (browser cache): FA-R89.

Reload with Ctrl+F5 first.

1. Logged out, a public report's page (e.g. `14-07`): click the thumbnail: the PDF opens.
2. As editor, `https://arctic.sustain.dtu.dk/find/publications/add/reports_from_file/`: the template link downloads `ARTEK_report_list.xlsx` with a Help sheet.
3. As editor, upload a copy of the template with one row that has an unknown author initials (e.g. `zzzz`): the page lists the problem with sheet and row, and no report is created. Optional: upload one valid row with a test number, check the report, delete it.
4. `https://arctic.sustain.dtu.dk/find/api/report/?author_id=abc` gives 400.

## 7. PDF upload in production (T8, you)

- [x] Done (2026-11-20): a 100 MB PDF is refused by the form with "File cannot exceed 50 Mb" (the form's own limit, `forms/publication.py:560`); upload itself works (~20 MB in 2026.3.1). Raising the limit: FA-R88.

As editor, open the edit form of a test report and upload a large PDF (~50 MB). If it fails, note the size, the error page and the time; the main session then checks Django's upload settings and nginx `client_max_body_size` / timeouts in web_server. Delete the test report afterwards.

Report back which steps passed; the main session then closes the plan (roadmap, archive).
