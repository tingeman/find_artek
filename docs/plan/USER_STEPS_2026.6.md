# User steps: release 2026.6 (Django 5.2 LTS, PLAN_django-5 T8 and T9)

Branch `agent-django-5` holds T1-T7 of [PLAN_django-5_COMPLETE.md](../archive/PLAN_django-5_COMPLETE.md), with `develop/main` merged in. It is not on `develop/main` yet: step 1 checks it in the dev stack, step 2 fast-forwards it.

What changes for users:

- Nothing visible on purpose: the same pages, forms, API and login.
- `/find/publications/accounts/logout/` is gone (nothing linked it; the menu's logout is the CAS logout `/find/logout`, unchanged).
- A login link with `?next=` pointing to another site gives 400 (before: the user was sent to that site after the CAS login).
- The Swagger UI (`/find/swagger/`) "Django Logout" button works (it went to the removed URL).
- Report form: a person's initials (DTU username, e.g. `thin`) typed instead of picked from the dropdown are matched in the "disambiguate person" step (before: only "create new person").

Deployment impact (web_server):

- Django 4.2.30 → 5.2.19 LTS, Python 3.12.11 → 3.13.18, base image Debian 12 → 13 (trixie). The image is self-contained; the host needs nothing.
- No migration (`migrate --plan` shows none). No new env variable. Port, paths, user, entrypoint and cron unchanged.
- `tests/run.sh`: a `check --deploy` warning other than `security.W004`/`security.W008` now fails the build. Interface unchanged. Image ~46 MB larger (927 MB).

## 1. Dev checks (T8, you)

- [x] Done (2026-11-21): all checks pass, after the initials fix (`2315198`). Logout stops on DTU's logout page: expected, see item 6.

The dev stack already runs the branch (project `find_artek_develop`, started from the worktree). To rebuild it yourself:

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_agent-django-5
docker compose -p find_artek_develop -f docker-compose.yml -f docker-compose.develop.yml up -d --build
docker compose -p find_artek_develop -f docker-compose.yml -f docker-compose.develop.yml exec -T webapp-find-artek python -c "import django, sys; print(django.get_version(), sys.version.split()[0])"   # 5.2.19 3.13.18
```

At http://localhost:8098/ (Ctrl+F5 first):

1. Log in through CAS. Your roles show (the "Add" menu is there).
2. Add a test report with a PDF and a new person; edit it (the author autocomplete finds persons); delete it. Type your initials (`thin`) in the supervisor field without picking from the dropdown: the next step offers you.
3. A confidential report's PDF: opens logged in, refused logged out.
4. `/swagger/` and `/redoc/` load; in Swagger, "Django Logout" logs you out through CAS.
5. `/admin/` works.
6. The menu's logout ends on DTU's "you are logged out" page (DTU CAS does not follow the return address `?url=<front page>`; same before the upgrade, checked 2026-11-21). Back on the site you are logged out.

Tell the main session what passed; anything off is fixed on the branch before step 2.

## 2. Fast-forward `develop/main` (main session, with your OK)

- [x] Done (2026-11-21, main session): `develop/main` fast-forwarded to `d7aef5d`.

The main session reruns the checks on the branch tip and fast-forwards `develop/main` to it (`git merge --ff-only agent-django-5`).

## 3. Tag `2026.6` locally (you)

- [x] Done (2026-11-21, main session, with your OK): annotated tag on `d7aef5d`, local only. Push it with `git push origin develop/main 2026.6`.

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
git switch develop/main
git log --oneline -1                                     # the T7 commit or the merge, = agent-django-5
git tag -a 2026.6 -m "2026.6: Django 5.2 LTS, Python 3.13 (Phase 3)"
git push origin develop/main 2026.6
```

## 4. Build and test the bundle (you)

- [x] Done (2026-11-21, main session, with your OK): `RESULT: OK, bundle written, tests passed`, 22/22, `Ran 569 tests` OK; tarball_sha256 `97d42250f222a92391f91dc7d00d90f349c21ad00e4f30c2567f65313db52724` (221 MB), image_id `sha256:0853cf1a5c26...`, built 2026-11-21T08:40:51Z, git_sha `d7aef5dcee73`.

```bash
# WSL
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server
bash scripts/build_image.sh webapp_find_artek /mnt/c/thin/02_Code/docker_projects/find_artek_DEVELOP 2026.6
cat release-out/webapp_find_artek/webapp_find_artek-2026.6.manifest.txt
```

Expect `RESULT: OK, bundle written, tests passed`, 22/22, `Ran 569 tests` OK, and `INFO: Django, GDAL, GEOS: 5.2.19 3.10.3 ...`.

## 5. Publish to the releases share (you)

- [x] Done (2026-11-21, main session): tarball, `.sha256` and manifest copied; hash on the share matches the manifest.

```powershell
# PowerShell
$dst = '\\ait-pdfs\Qdrev\SUS\Groups\Arctic_backup\SUS-PArcWeb01\releases\webapp_find_artek'
Get-ChildItem $dst                                   # must not contain webapp_find_artek-2026.6.* yet
Copy-Item 'C:\thin\02_Code\docker_projects\dtu_sus_web_server\release-out\webapp_find_artek\webapp_find_artek-2026.6.*' $dst
Get-FileHash -Algorithm SHA256 "$dst\webapp_find_artek-2026.6.tar.gz"   # = tarball_sha256 in the manifest
```

## 6. releases.yml (web_server, you)

- [x] Done (2026-11-21, main session, with your OK): `version: "2026.6"`, tarball_sha256 from the manifest, 2026.5 kept commented out for rollback; committed on web_server `develop/main` (`0b4d515`, not pushed).

In `C:\thin\02_Code\docker_projects\dtu_sus_web_server\ansible\vars\releases.yml`: `version: "2026.6"`, `tarball_sha256` from the manifest; keep the 2026.5 entry commented out for rollback. Commit on web_server's `develop/main`.

## 7. Deploy the app (you)

- [x] Done (2026-11-21): `webapp_find_artek:2026.6` healthy, frontpage 200, Django 5.2.19 on Python 3.13.18, migrations unchanged (`0004`), no traceback or error in the log.

```bash
# WSL
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server/ansible
ansible-playbook -kK -i hosts playbook_install_webapp_find_artek.yml -v --ask-vault-pass
```

Server checks:

```bash
# SSH on sus-parcweb01
sudo docker ps --filter name=webapp-find-artek --format '{{.Names}}  {{.Image}}  {{.Status}}'      # webapp_find_artek:2026.6, healthy
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/find/publications/frontpage/          # 200
sudo docker exec webapp-find-artek python -c "import django, sys; print(django.get_version(), sys.version.split()[0])"   # 5.2.19 3.13.18
sudo docker exec webapp-find-artek python manage.py showmigrations publications | tail -1          # [X] 0004_publication_confidential (unchanged)
sudo docker logs --since 10m webapp-find-artek 2>&1 | grep -iE 'traceback|error' | head            # nothing
```

Rollback: put the `2026.5` entry back in `releases.yml` and rerun the playbook. No migration to reverse.

## 8. Functional checks in production (you)

- [x] Done (2026-11-21): checks 1-4 pass (confidential report 12-05 / pk 382: login redirect and 404 for the PDF logged out, opens as editor). Check 5 (thumbnail cron next morning) not yet run when the plan was closed.

Ctrl+F5 first, on `https://arctic.sustain.dtu.dk/find/`:

1. Front page and report list load logged out.
2. Log in through CAS (the service URL carries `/find`): you land back on the page you came from, with your roles.
3. A confidential report's PDF: opens logged in, refused logged out; a public report's PDF opens logged out.
4. `/find/api/report/` returns JSON; `/find/swagger/` loads.
5. Next morning: the thumbnail cron ran (`sudo docker logs --since 24h webapp-find-artek 2>&1 | grep -i thumbnail | tail -3` on the server).

The plan was closed 2026-11-21 ([STATUS](../archive/STATUS_django-5_COMPLETE.md)); this file stays in `docs/plan/` until step 9 is done, then the main session archives it.

## 9. After closing (you)

- [ ] a. Thumbnail cron: check 5 of step 8 (the morning after the deploy).
- [ ] b. Push find_artek `develop/main` and the tag:

  ```powershell
  # PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
  git push origin develop/main 2026.6
  ```

- [ ] c. Fast-forward `main` to the deployed tag (FA5) and push it:

  ```powershell
  # PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
  git switch main
  git merge --ff-only 2026.6
  git push origin main
  git switch develop/main
  ```

- [ ] d. Push web_server `develop/main` (`0b4d515`, the `releases.yml` change):

  ```powershell
  # PowerShell, in C:\thin\02_Code\docker_projects\dtu_sus_web_server
  git log --oneline -1 develop/main      # 0b4d515 find_artek: release 2026.6 in releases.yml
  git push origin develop/main
  ```

- [ ] e. Optional cleanup. The dev stack runs from the `agent-django-5` worktree; start it from your checkout first (same project name, so it replaces those containers; the database volume stays).

  ```powershell
  # PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
  docker compose -p find_artek_develop -f docker-compose.yml -f docker-compose.develop.yml up -d --build
  git worktree remove ..\find_artek_agent-django-5         # if it refuses because of the copied .dev.env: add --force
  git branch -d agent-django-5                              # merged into develop/main
  git worktree remove ..\find_artek_agent-test-coverage    # old Phase 2 worktree, same
  docker rmi find_artek:t5-before                           # image from the T5 size comparison
  ```

Tell the main session when step 9 is done; it then archives this file.
