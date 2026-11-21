# User steps: release 2026.7 (PLAN_release-2026-7 T9 and T10)

Branch `agent-release-2026-7` holds T1-T8, T11 and T12 of [PLAN_release-2026-7.md](PLAN_release-2026-7.md), with `develop/main` merged in (`5528305`); tip `61c330c`. It is not on `develop/main` yet: step 1 checks it in the dev stack, step 2 fast-forwards it.

Checks on the branch tip (2026-11-21, main session): `check` clean, `makemigrations --check` no changes, 718 Django tests OK; `tests/run.sh` ALL 22 TESTS PASSED (implementer, on `61c330c`).

What changes for users:

- **Uploads:** report PDFs and appendices up to 300 MB per file (before: refused above 50 MB by the browser). A refused appendix now says why.
- **Report list and map:** load in well under a second (before: 2-3 s) and always show the current data; a deleted report no longer stays in the list.
- **Administration:** the header's "Add" drop-down is replaced by a link "Administration" to a page with picture tiles, as in the classic version. Working: Add report, Import reports from Excel; greyed with the reason: Add feature (open a report), Add person, Import features from Excel; Django admin for staff.
- **Person markers (ARTEK editors only):** a red (!) or (?) next to authors and supervisors whose person was created although similar persons existed, on the report page and in the report list; the person page lists the marked links. "Confirm person" clears the markers. "Merge duplicates…" merges other persons into this one (confirmation page first; can't be undone in the app).
- **Report form:** typed initials or a study number are also looked up in the DTU directory; a hit not yet in the database is offered as "[DTU directory]" and added (name, initials/study number, position, department; no email) when the report is saved. The edit page is titled "Edit report" and shows the report summary; changing the year no longer replaces the report number in edit mode.
- **Person autocomplete** (`/find/publications/test/autocomplete/person/`): logged-in users only; anonymous users get 403.
- **403 pages** show their explanation again.

Deployment impact (web_server):

- **Migration `0005_person_merge_person_permission`:** adds the permission `publications.merge_person` (one `auth_permission` row) and grants it to the group `artek_editor` (one group-permission link). No report, person or user row changes. Reversible (`migrate publications 0004`). The playbook's `migrate --plan`/`migrate` applies it.
- **Thumbnail cron:** `generate_thumbnails` now exits 1 when publications fail. Production logs `ERROR: thumbnail generation failed with exit code 1` every night until the PDFs of 01-06 and 14-28 are fixed (FA-R69). web_server's cron post-check (`ansible/tasks/find_artek_checks.yml`) only checks the daemon and the cron file, so the deploy is unaffected.
- **Logging:** new logger `publications.persons` (INFO, console and file): one line per person merge, with pks and counts, no names.
- **Static scripts:** the three scripts changed in this release load as `...js?v=2026.7` (`STATIC_ASSET_VERSION` in settings.py), so browsers don't keep the old cached copies. File names unchanged.
- **LDAP:** the report form now asks the directory (existing bind settings, 5 s timeout); unreachable means no directory choice, one WARNING in the log.
- No new env variable. Port, paths, user, entrypoint, cron schedule and the `tests/run.sh` interface unchanged. nginx already allows 300 MB on `/find/`.
- Open question for web_server: does nginx gzip `application/json` on `/find/`? The feature list is 660 KB uncompressed.

## 1. Dev checks (T9, you)

- [ ] Done.

The dev stack already runs the branch (project `find_artek_develop`, started from the worktree). Apply the new migration to your dev database first (it only adds the permission and the group grant):

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_agent-release-2026-7
$DC = "docker compose -p find_artek_develop -f docker-compose.yml -f docker-compose.develop.yml"
Invoke-Expression "$DC up -d --build"
Invoke-Expression "$DC exec -T webapp-find-artek python manage.py migrate --plan --settings find_artek.development_settings"   # only publications.0005
Invoke-Expression "$DC exec -T webapp-find-artek python manage.py migrate --settings find_artek.development_settings"
Invoke-Expression "$DC exec -T webapp-find-artek python manage.py showmigrations publications --settings find_artek.development_settings"   # [X] 0005_person_merge_person_permission
```

Round 1 (2026-11-21): 1 passed; 2 passed after a hard reload (old cached script, fixed by T11); 4 passed; 3 not reported; 5 and 6 and the rest are rechecked below after T11/T12; 7 and 8 not yet run.

Round 2: rebuild first (`up -d --build` above, the migration is already applied). At http://localhost:8098/, logged in through CAS, once with DevTools open: right-click reload, "Empty cache and hard reload":

1. **Header:** "Administration" instead of "Add". The page shows the tiles; Add report and Import reports from Excel open their forms; the greyed tiles show their reason. Narrow the window to phone width: the tiles wrap, the mobile menu has "Administration".
2. **Upload:** add a test report with a PDF over 50 MB (and below 300 MB); upload an appendix over 50 MB on its page. Both are accepted.
3. **Report list and map:** load fast. Delete the test report: it is gone from the list on the next load, without logging out. Edit a report's title: the list shows the new title at once.
4. **Markers** (you are `artek_editor`): add a test report and type a new author similar to an existing person (e.g. an existing last name with a different first name), choose "create new person". The report page and the list show (?) or (!) next to that author, with a tooltip and a legend; in the legend only the ! and ? are red and bold, the parentheses black.
4a. **Report form (T11):** the header menu has the same spacing as on the other pages. "Edit report" on an existing report: titled "Edit report", the report summary above the form; changing the year keeps the report number.
5. **Confirm:** click the marker: the merge page has "Not a duplicate: Confirm person"; it goes to the person page and clears the markers; the report page shows no marker afterwards. (The person page's own "Confirm person" box does the same.)
6. **Merge:** repeat step 4 to make a test duplicate of a test person, open "Merge duplicates…" on the original, tick the duplicate, check the confirmation page (links moved, fields filled), and merge. The report now links to the original; the duplicate's person page gives 404. Use test persons, not real ones. Delete the test reports afterwards.
6a. **DTU directory (T12):** add a test report, type `asska` as supervisor: the person step offers "<Name> (asska) [DTU directory]" with position and department; choose it; the review shows "(asska, from the DTU directory)"; save: the person page has the initials, position and department, and no marker. Type `asska` again in another report: now the database person with the badge "In DTU directory", no directory choice. A full name (with a space) shows no directory section. Optional: a student's study number. Delete the test reports afterwards (the person `asska` from round 1 can be merged into the new one, or deleted in the Django admin).
7. **Autocomplete:** the author field in the report form still suggests persons. Logged out, http://localhost:8098/publications/test/autocomplete/person/?term=a gives 403.
8. **PDF metadata** (read-only; the output contains names and study numbers, keep it in your terminal):

   ```powershell
   # PowerShell, in C:\thin\02_Code\docker_projects\find_artek_agent-release-2026-7
   Invoke-Expression "$DC exec -T webapp-find-artek python manage.py extract_pdf_metadata --evaluate 50 --settings find_artek.development_settings"
   Invoke-Expression "$DC exec -T webapp-find-artek python manage.py extract_pdf_metadata --unowned --settings find_artek.development_settings"
   ```

   Tell the main session only the hit rates of `--evaluate` (title, year, study numbers, no text layer) and roughly how many orphan PDFs got a usable title.

Tell the main session what passed; anything off is fixed on the branch before step 2.

## 2. Fast-forward `develop/main` (main session, with your OK)

- [ ] Done.

The main session reruns the checks on the branch tip and fast-forwards `develop/main` to it (`git merge --ff-only agent-release-2026-7`).

## 3. Tag `2026.7` (you, or the main session with your OK)

- [ ] Done.

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
git switch develop/main
git log --oneline -1                                     # = agent-release-2026-7
git tag -a 2026.7 -m "2026.7: upload limit, fast lists, Administration page, person markers and merge"
git push origin develop/main 2026.7
```

## 4. Build and test the bundle (you)

- [ ] Done.

```bash
# WSL
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server
bash scripts/build_image.sh webapp_find_artek /mnt/c/thin/02_Code/docker_projects/find_artek_DEVELOP 2026.7
cat release-out/webapp_find_artek/webapp_find_artek-2026.7.manifest.txt
```

Expect `RESULT: OK, bundle written, tests passed`, 22/22, `Ran 685 tests` OK.

## 5. Publish to the releases share (you)

- [ ] Done.

```powershell
# PowerShell
$dst = '\\ait-pdfs\Qdrev\SUS\Groups\Arctic_backup\SUS-PArcWeb01\releases\webapp_find_artek'
Get-ChildItem $dst                                   # must not contain webapp_find_artek-2026.7.* yet
Copy-Item 'C:\thin\02_Code\docker_projects\dtu_sus_web_server\release-out\webapp_find_artek\webapp_find_artek-2026.7.*' $dst
Get-FileHash -Algorithm SHA256 "$dst\webapp_find_artek-2026.7.tar.gz"   # = tarball_sha256 in the manifest
```

## 6. releases.yml (web_server, you)

- [ ] Done.

In `C:\thin\02_Code\docker_projects\dtu_sus_web_server\ansible\vars\releases.yml`: `version: "2026.7"`, `tarball_sha256` from the manifest; keep the 2026.6 entry commented out for rollback. Commit on web_server's `develop/main`.

## 7. Deploy the app (you)

- [ ] Done.

```bash
# WSL
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server/ansible
ansible-playbook -kK -i hosts playbook_install_webapp_find_artek.yml -v --ask-vault-pass
```

The playbook takes the pre-deploy dump and runs `migrate --plan` (expect only `publications.0005_person_merge_person_permission`) and `migrate`.

Server checks:

```bash
# SSH on sus-parcweb01
sudo docker ps --filter name=webapp-find-artek --format '{{.Names}}  {{.Image}}  {{.Status}}'      # webapp_find_artek:2026.7, healthy
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/find/publications/frontpage/          # 200
sudo docker exec webapp-find-artek python manage.py showmigrations publications | tail -1          # [X] 0005_person_merge_person_permission
sudo docker logs --since 10m webapp-find-artek 2>&1 | grep -iE 'traceback|error' | head            # nothing
```

Rollback: put the `2026.6` entry back in `releases.yml`, then `sudo docker exec webapp-find-artek python manage.py migrate publications 0004` **before** rerunning the playbook (2026.6 doesn't know 0005), or restore the pre-deploy dump.

## 8. Functional checks in production (you)

- [ ] Done.

Ctrl+F5 first, on `https://arctic.sustain.dtu.dk/find/`:

1. Front page, report list and map load logged out, fast.
2. Log in through CAS: "Administration" in the header opens the tile page.
3. A confidential report's PDF: opens logged in, refused logged out; a public report's PDF opens logged out.
4. `/find/api/report/` returns JSON; `/find/swagger/` loads.
5. As `artek_editor`: markers appear where persons are marked (if any); open one person page with markers and check the list (don't confirm or merge real persons unless you mean it).
6. Logged out: `/find/publications/test/autocomplete/person/?term=a` gives 403.
7. Next morning: `sudo docker logs --since 24h webapp-find-artek 2>&1 | grep -F '[thumbnails]' | tail -4` shows the 2 known errors and `exit code 1` (expected until FA-R69's data part is done).

## 9. After closing (you)

- [ ] a. Fast-forward `main` to the deployed tag (FA5) and push it:

  ```powershell
  # PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
  git merge-base --is-ancestor main 2026.7; if ($?) { git branch -f main 2026.7 }
  git push origin main
  ```

- [ ] b. Push web_server `develop/main` (the `releases.yml` change). web_server's remote is `github`:

  ```powershell
  # PowerShell, in C:\thin\02_Code\docker_projects\dtu_sus_web_server
  git push github develop/main
  ```

- [ ] c. Optional cleanup, after step 9 of [USER_STEPS_2026.6_COMPLETE.md](../archive/USER_STEPS_2026.6_COMPLETE.md):

  ```powershell
  # PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
  git worktree remove ..\find_artek_agent-release-2026-7    # if it refuses because of the copied .dev.env: add --force
  git branch -d agent-release-2026-7                         # merged into develop/main
  ```

Tell the main session when step 9 is done; it then archives this file.
