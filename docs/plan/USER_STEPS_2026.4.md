# User steps: release 2026.4 (confidential reports and checked media, PLAN_confidential T8)

Branch `agent-confidential` is at `0b13b6e` (2026-11-20): T1-T7 of [PLAN_confidential.md](PLAN_confidential.md) plus a merge of `develop/main` (`2026.3.1` and docs). Gate on the branch: 22/22, Django step 316 tests. Step 0 puts it on `develop/main`.

What changes for users:

- Reports have a `confidential` flag (migration 0004 sets it where the comment says "confidential"; 2 reports in the dev copy: `12-05`, `15-28`). Anyone who may edit a report can set it in the add/edit form.
- One visibility rule for pages, the API and files: anonymous users see verified, non-confidential reports; logged-in users also see unverified ones, but confidential ones only when listed on them; `artek_editor` and superusers see everything. A hidden report's page sends anonymous users to the login and gives logged-in users 404.
- Every file under `/find/media/` is checked by Django (after the nginx change in step 7). Files no report or feature owns (64 in the dev copy, see the status file) become editor-only; none of them is linked from a page.
- Cached report data in the browser is dropped when the login changes.

Deployment impact (web_server):

- Migration `publications.0004_publication_confidential` (adds a column, sets it on rows whose comment matches; comments unchanged). The playbook takes the pre-deploy dump.
- nginx: add the internal location `/find/_protected_media/`, remove the `/find/media/` alias (step 7). Until step 7 nginx still serves media itself: nothing breaks, the file check just isn't active yet.
- No new env variables, requirements and Dockerfile unchanged. `MEDIA_ACCEL_REDIRECT_PREFIX` is a plain setting.

## 0. Fast-forward `develop/main` (main session, with your OK)

- [x] Done (2026-11-20, main session): `develop/main` fast-forwarded to `debfb94`.

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
git merge --ff-only agent-confidential
git log --oneline -1 develop/main                     # the same commit as agent-confidential (a merge of develop/main docs on top of 0b13b6e)
```

## 1. Tag `2026.4` locally

- [x] Done (2026-11-20, main session, with your OK): tag on `debfb94`.

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
git tag -a 2026.4 -m "find_artek 2026.4: confidential reports, one visibility rule, checked media files" develop/main
git show --no-patch --format='%h %s' '2026.4^{commit}'
```

## 2. Build and test the bundle

- [x] Done (2026-11-20, main session): `RESULT: OK`, 22/22, `Ran 316 tests`; tarball_sha256 `8b4c9b7339a449b46cd86f6b22817e87530c71eaeff9c013eb70083e06215a82`, image_id `sha256:1228d5763e4e...`, built 2026-11-20T06:54:13Z.

```bash
# WSL
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server
bash scripts/build_image.sh webapp_find_artek /mnt/c/thin/02_Code/docker_projects/find_artek_DEVELOP 2026.4
cat release-out/webapp_find_artek/webapp_find_artek-2026.4.manifest.txt
```

Expect `RESULT: OK`, 22 tests, and the Django step `Ran 316 tests`. Paste the manifest.

## 3. Publish to the releases share

- [x] Done (2026-11-20, main session): copied, hash on the share matches the manifest.

```powershell
# PowerShell
$dst = '\\ait-pdfs\Qdrev\SUS\Groups\Arctic_backup\SUS-PArcWeb01\releases\webapp_find_artek'
Get-ChildItem $dst                                   # must not contain webapp_find_artek-2026.4.* yet
Copy-Item 'C:\thin\02_Code\docker_projects\dtu_sus_web_server\release-out\webapp_find_artek\webapp_find_artek-2026.4.*' $dst
Get-FileHash -Algorithm SHA256 "$dst\webapp_find_artek-2026.4.tar.gz"   # = tarball_sha256 in the manifest
```

## 4. releases.yml (web_server)

- [x] Done (2026-11-20): entry and comment written by the main session; **not committed** (web_server config: you commit it).

`ansible/vars/releases.yml`, `webapp_find_artek`: `version: "2026.4"`, `tarball_sha256` from the manifest. Paste the manifest and the main session writes the comment (previous: 2026.3.1, tarball_sha256 `8dfccba315f8fc1df510c681f3aaeb085859458d3b518a90d0cebd02dca14ad7`). The env file needs no change. Commit.

## 5. Deploy the app

- [x] Done (2026-11-20): deployed, host checks pass. `check_media_access` in production: 2630 files, public 2554, restricted 14 (incl. 4 temp), unowned 62: the same 16 mangled `ø`/`Ø` names as in dev (so broken in production already), the 1996-2000 orphans, and old upload names of reports that now have their PDF under the number (`01-06a`, `11-30_1`, title-named 2014/2015 PDFs, checked by title in the dev DB). Nothing linked loses access.

```bash
# WSL, web_server with step 4 committed
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server/ansible
ansible-playbook -kK -i hosts playbook_install_webapp_find_artek.yml -v --ask-vault-pass
```

The playbook shows `migrate --plan` with `publications.0004_publication_confidential` and takes a dump first (web_server `docs/deploy/find_artek_admin.md`, section 4).

Server checks:

```bash
# SSH on sus-parcweb01
sudo docker ps --filter name=webapp-find-artek --format '{{.Names}}  {{.Image}}  {{.Status}}'      # webapp_find_artek:2026.4, healthy
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/find/publications/frontpage/          # 200
sudo docker exec webapp-find-artek python manage.py showmigrations publications | tail -1          # [X] 0004_publication_confidential
sudo docker exec webapp-find-artek python manage.py shell -c "from publications.models import Publication as P; print(list(P.objects.filter(confidential=True).values_list('number', flat=True)))"
                                                                                                  # ['12-05', '15-28'] in the dev copy; more if comments changed since
sudo docker exec webapp-find-artek python manage.py check_media_access --list-unowned
```

Paste the `check_media_access` output. The main session compares it with the dev copy (64 unowned; 16 of them are `ø`/`Ø` names mangled in the dev copy, see the status file). Before step 7, any unowned file that a page links would lose public access; the dev copy has none.

Rollback: reverse the migration with the 2026.4 container **first** (2026.3.1 doesn't know the column, and Django sets no database default, so adding a report would fail): `sudo docker exec webapp-find-artek python manage.py migrate publications 0003`, then put the `2026.3.1` entry back in `releases.yml` and rerun the playbook. If step 7 is done, undo it first.

## 6. Functional checks in the browser (app)

- [x] Done (2026-11-20): all browser checks pass (`/report/382/` → login, public pages open, Confidential badge shown).

Reload with Ctrl+F5 first.

1. Logged out: `https://arctic.sustain.dtu.dk/find/publications/report/382/` (`12-05`) → login page. A public report's page (e.g. `14-07`) opens as before, PDF link works.
2. As editor or superuser: `12-05` shows the "Confidential" badge; its edit form has the "Confidential" checkbox ticked.
3. As editor: open a test report's edit form, tick "Confidential", the review step shows the change, save. Log out: the report is gone from lists and the API (`/find/api/report/`). Log in, untick, save (or delete the test report).
4. Log in and out in the same tab: the report list reloads its data (no reports from the previous login).

## 7. nginx: media through Django (web_server)

- [ ] Done. Edit made by the main session 2026-11-20 in web_server `docker/services/nginx/nginx.conf` (block replaced as below, `nginx -t` passes with the pinned image and a throwaway cert); **not committed**: review, commit, run the nginx playbook.

Both edits together in `docker/services/nginx/nginx.conf` of web_server (deploy-contract skill, section "Media files"; never remove the alias without adding the internal location, or every media file gives 404):

1. Replace the block at `nginx.conf:233-238`

   ```nginx
           # No directory listing: media holds (weakly) confidential reports. Files stay downloadable
           # by their direct URL. Access control for media is planned (find_artek roadmap FA-R30).
           location /find/media/ {
               alias /usr/share/nginx/staticfiles/find_artek_static/media/;   # Trailing slash needed when location ends with /
               try_files $uri $uri/ =404;
           }
   ```

   with

   ```nginx
           # find_artek media: /find/media/ goes to Django (location /find/), which checks access and
           # answers with X-Accel-Redirect to this internal location (find_artek FA-R30, FA-R75).
           location /find/_protected_media/ {
               internal;
               alias /usr/share/nginx/staticfiles/find_artek_static/media/;   # Trailing slash needed when location ends with /
           }
   ```

2. The comment at `nginx.conf:221` ("find_artek only uses /find/static/ and /find/media/") stays true.

Commit, then:

```bash
# WSL, web_server with the nginx change committed
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server/ansible
ansible-playbook -kK -i hosts playbook_install_nginx.yml -v --ask-vault-pass
```

A few seconds of downtime for all sites. Rollback: restore the old block and rerun the nginx playbook.

## 8. Functional checks (media)

- [ ] Done

```bash
# WSL (from the DTU network or VPN)
B=https://arctic.sustain.dtu.dk/find/media
curl -s -o /dev/null -w '%{http_code} %{content_type}\n' $B/reports/2014/14-07.pdf                       # 200 application/pdf
curl -s -o /dev/null -w '%{http_code}\n' -H 'Range: bytes=0-99' $B/reports/2014/14-07.pdf                # 206
curl -s -o /dev/null -w '%{http_code}\n' $B/reports/2012/12-05.pdf                                       # 404 (confidential, unverified)
curl -s -o /dev/null -w '%{http_code}\n' $B/reports/2015/15-28.pdf                                       # 404 (confidential, unverified)
curl -s -o /dev/null -w '%{http_code}\n' $B/reports/2014/thumbs/14-07_thumb.jpg                          # 200
curl -s -o /dev/null -w '%{http_code}\n' https://arctic.sustain.dtu.dk/find/_protected_media/reports/2014/14-07.pdf   # 404 (internal)
curl -s -o /dev/null -w '%{http_code}\n' $B/reports/1996/96-02.pdf                                       # 404 (unowned)
time curl -s --limit-rate 200k -o /dev/null -w '%{http_code} %{size_download}\n' $B/reports/2009/09-38.pdf   # 200 26063012, ~130 s
curl -s --limit-rate 200k --max-time 20 -o /tmp/0938.pdf $B/reports/2009/09-38.pdf; curl -s -C - -o /tmp/0938.pdf -w '%{http_code}\n' $B/reports/2009/09-38.pdf; ls -l /tmp/0938.pdf; rm /tmp/0938.pdf
                                                                                                         # 206, then 26063012 bytes
```

Then in the browser, logged in as editor: the PDF of `12-05` opens. The report page of a public report shows its thumbnail and PDF link as before.

## 9. After the deploy

- [ ] Done

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
git branch -f main 2026.4
```

Tell the main session; it closes PLAN_confidential (roadmap, archive, worktree) and starts PLAN_test-coverage. web_server: add the media checks of step 8 to "Functional checks per service" in its roadmap (deploy-contract skill lists them).
