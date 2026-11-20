# User steps: release 2026.3 (registration, PLAN_registration T11)

`develop/main` is at `7ae8a69` (2026-11-20): the registration work of [PLAN_registration.md](PLAN_registration.md) (T1-T10, T12-T14, T16, match flags) on top of `2026.2.1`, plus the LDAP bind fix `7ae8a69` (bind as `<LDAP_BIND_USER>@win.dtu.dk`; the old DN under `OU=BYG` failed since the service account moved to `OU=SUS service accounts`, so every LDAP lookup in production failed too). Gate on the branch: 22/22, Django step 228 tests.

What changes for users:

- Roles: every CAS login gets group `dtu_user`; `artek_staff` / `artek_editor` only from the AD groups in `LDAP_GROUP_ARTEK_STAFF` / `LDAP_GROUP_ARTEK_EDITOR` (empty = nobody; superusers unaffected). Name and e-mail from AD at every login.
- Every write view checks permissions (405 / login / 404 / 403); verify/unverify are POST buttons; `/debug-root/` is gone.
- Report form: typed keywords created on save, topics list-only, PDF moved after the save, temp upload removed, typed new authors/supervisors work (new persons created on save, classic match flags set); "Use As-Is" button removed.
- "Add" menu for staff and editors. Study numbers and student e-mails hidden from anonymous users.

Deployment impact (web_server):

- **Migration** `publications.0003_registration_groups`: data only, creates the three groups and their permission links; no existing row changes (the production copy has no auth groups). The playbook's normal path applies (dump, `migrate --plan`, `migrate`).
- **New env variables** `LDAP_GROUP_ARTEK_STAFF`, `LDAP_GROUP_ARTEK_EDITOR` (default empty) for `webapp_find_artek.env`; already in web_server's `docs/deploy/secrets.md` (`89ba8d9`, 2026-11-20).
- **LDAP bind** as `<LDAP_BIND_USER>@win.dtu.dk` (UPN) instead of a DN; `LDAP_BIND_USER` / `LDAP_BIND_PASSWORD` unchanged. Fixes the LDAP lookups that fail in production today (person lookup, Excel import).
- The AD lookup now runs at every CAS login (bind with `LDAP_BIND_USER` / `LDAP_BIND_PASSWORD` to `ldaps://win.dtu.dk`). If it fails, the login still works and a warning goes to the container log.
- nginx: `client_max_body_size 300M` on `/find/` already (checked 2026-11-19). Port, paths, user, entrypoint and cron unchanged.

## 0. Decide: wait for the AD groups?

- [x] Done: **wait** (decided 2026-11-19). The groups exist since 2026-11-19 (`SUS-IT-Artek-Staff-53763`, `SUS-IT-Artek-Editor-53764`; DNs looked up in AD, in step 4). Steps 1-7 can start.

## 1. Tag `2026.3` locally

- [x] Done (2026-11-20)

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
git log --oneline -3 develop/main                     # expect 7ae8a69, or docs commits on top of it
git tag -a 2026.3 -m "find_artek 2026.3: registration (roles from AD, permission checks, report form, Add menu)" develop/main
git show --no-patch --format='%h %s' '2026.3^{commit}'
```

## 2. Build and test the bundle

- [x] Done (2026-11-20)

```bash
# WSL
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server
bash scripts/build_image.sh webapp_find_artek /mnt/c/thin/02_Code/docker_projects/find_artek_DEVELOP 2026.3
cat release-out/webapp_find_artek/webapp_find_artek-2026.3.manifest.txt
```

Expect `RESULT: OK`, 22 tests, and the Django step `Ran 228 tests`. Paste the manifest.

## 3. Publish to the releases share

- [x] Done (2026-11-20)

```powershell
# PowerShell
$dst = '\\ait-pdfs\Qdrev\SUS\Groups\Arctic_backup\SUS-PArcWeb01\releases\webapp_find_artek'
Get-ChildItem $dst                                   # must not contain webapp_find_artek-2026.3.* yet
Copy-Item 'C:\thin\02_Code\docker_projects\dtu_sus_web_server\release-out\webapp_find_artek\webapp_find_artek-2026.3.*' $dst
Get-FileHash -Algorithm SHA256 "$dst\webapp_find_artek-2026.3.tar.gz"   # = tarball_sha256 in the manifest
```

## 4. Env file and releases.yml (web_server)

- [x] Done (2026-11-20)

1. In the secrets vault, `webapp_find_artek.env`: add two lines (full DNs, no quotes):
   ```
   LDAP_GROUP_ARTEK_STAFF=CN=SUS-IT-Artek-Staff-53763,OU=SecurityGroups,OU=SUS,OU=DTUBasen,DC=win,DC=dtu,DC=dk
   LDAP_GROUP_ARTEK_EDITOR=CN=SUS-IT-Artek-Editor-53764,OU=SecurityGroups,OU=SUS,OU=DTUBasen,DC=win,DC=dtu,DC=dk
   ```
   (`docs/deploy/secrets.md` in web_server already lists both.)
2. `ansible/vars/releases.yml`, `webapp_find_artek`: `version: "2026.3"`, `tarball_sha256` from the manifest, comment as for 2026.2.1 (previous: 2026.2.1, commit `372719be3cd4`, tarball_sha256 `c6edca0f91f60d490e043ce04309d4764fe855fc2f70a655094582b525d97c25`; one migration, data only; LDAP bind by UPN). Commit.

## 5. Deploy

- [x] Done (2026-11-20)

```bash
# WSL, web_server with step 4 committed
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server/ansible
ansible-playbook -kK -i hosts playbook_install_webapp_find_artek.yml -v --ask-vault-pass
```

The playbook shows `migrate --plan` with `publications.0003_registration_groups` and takes a dump first.

Server checks:

```bash
# SSH on sus-parcweb01
sudo docker ps --filter name=webapp-find-artek --format '{{.Names}}  {{.Image}}  {{.Status}}'      # webapp_find_artek:2026.3, healthy
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/find/publications/frontpage/          # 200
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/find/publications/report/add/         # 302 (to the login)
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/find/debug-root/                       # 404
sudo docker exec webapp-find-artek python manage.py showmigrations publications | tail -2          # [X] 0003_registration_groups
```

Rollback: put the `2026.2.1` entry back in `releases.yml` and rerun the playbook. Migration 0003 can stay (2026.2.1 ignores the groups) or be reversed with `migrate publications 0002` before the rollback (removes the three groups).

## 6. Functional checks in the browser

- [ ] Done. 2026-11-20: checks 1 and 2 passed; 7 open (AD groups had no members at the first login; members added 2026-11-20, waiting for AD replication); 3, 5, 6 not run yet. **Check 4 failed** (2026-11-20 00:05): with a PDF, "Create person" in the person step posted back to `report/add/` and showed an empty form; nothing saved, the PDF left in `media/temp/1795133116`. Cause: `file-upload.js` sends the form by XHR and copies the redirected page into the current one, so the person step's forms (no `action`) posted to the address bar URL. Fix `72e3242` on `agent-fixes` (2026.3.1).

1. Logged out: a person page shows no study number and no student e-mail; no "Add" menu; `/find/publications/report/add/` sends you to the DTU login.
2. Log in with your own account, then the admin user page (`/find/admin/auth/user/`): your user has group `dtu_user`, first/last name and e-mail filled in. If not, look for a `publications.roles` warning in `sudo docker logs webapp-find-artek` (AD lookup failed).
3. A student account (if one is at hand): username `sNNNNNN`, group `dtu_user`, name/e-mail set; no "Add" menu; `/find/publications/report/add/` → 403.
4. As superuser (or editor once the groups exist): "Add" menu → "Add report". Add a test report with a typed new author, an existing supervisor, a new keyword and a PDF of ~20 MB (retests the production PDF bug, FA-R12/FA-R20). Expected: the person step asks about the typed name, the review shows "(new person)", the report is saved with the PDF and a number.
5. Logged out: the test report is not shown (access denied) and not in the person's list. Logged in: verify it with the button, then delete it.
6. On the server: `media/temp/` has no new folder from the test (`sudo ls -lt /mnt/Qdrev-arctic-web-data/staticfiles/find_artek_static/media/temp/ | head -3`).
7. Log in as a member of the AD groups (log out and in again after being added; the role is set at login): the admin user page shows `artek_staff` / `artek_editor`, and the "Add" menu appears. A user in neither group has neither role.

## 7. After the deploy

- [ ] Done

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
git branch -f main 2026.3
```

Tell the main session; it closes PLAN_registration (roadmap, archive).
