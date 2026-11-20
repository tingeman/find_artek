# User steps: fix release 2026.3.1 (report form with a PDF)

`develop/main` is at `84a5273` (2026-11-20): `2026.3` (`9ba6b2c`) plus docs commits and the fix `84a5273`. Gate on the branch: 22/22, Django step 229 tests. Checked by you in the dev stack 2026-11-20 (report with a PDF and a new person saved).

What changes for users:

- Adding or editing a report **with a PDF** and a typed new author/supervisor works again. In 2026.3 "Create person" (or choosing an existing person) in the person step went back to an empty add form and nothing was saved (2026.3 check 4). Cause: `file-upload.js` sends the form in the background for the progress bar and copied the redirected page into the current one, so the address bar stayed on `report/add/` and the step's forms (no `action`) posted there. Now the browser goes to the redirected page, and the step's forms post to the step URL.

Deployment impact (web_server): none beyond the version. No migration, no new env variables, requirements and Dockerfile unchanged.

## 1. Tag `2026.3.1` locally

- [ ] Done

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
git log --oneline -3 develop/main                     # expect 84a5273, or docs commits on top of it
git tag -a 2026.3.1 -m "find_artek 2026.3.1: report form with a PDF and a new person works again" develop/main
git show --no-patch --format='%h %s' '2026.3.1^{commit}'
```

## 2. Build and test the bundle

- [ ] Done

```bash
# WSL
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server
bash scripts/build_image.sh webapp_find_artek /mnt/c/thin/02_Code/docker_projects/find_artek_DEVELOP 2026.3.1
cat release-out/webapp_find_artek/webapp_find_artek-2026.3.1.manifest.txt
```

Expect `RESULT: OK`, 22 tests, and the Django step `Ran 229 tests`. Paste the manifest.

## 3. Publish to the releases share

- [ ] Done

```powershell
# PowerShell
$dst = '\\ait-pdfs\Qdrev\SUS\Groups\Arctic_backup\SUS-PArcWeb01\releases\webapp_find_artek'
Get-ChildItem $dst                                   # must not contain webapp_find_artek-2026.3.1.* yet
Copy-Item 'C:\thin\02_Code\docker_projects\dtu_sus_web_server\release-out\webapp_find_artek\webapp_find_artek-2026.3.1.*' $dst
Get-FileHash -Algorithm SHA256 "$dst\webapp_find_artek-2026.3.1.tar.gz"   # = tarball_sha256 in the manifest
```

## 4. releases.yml (web_server)

- [ ] Done

`ansible/vars/releases.yml`, `webapp_find_artek`: `version: "2026.3.1"`, `tarball_sha256` from the manifest. Paste the manifest and the main session writes the comment (previous: 2026.3, commit `9ba6b2cd6695`, tarball_sha256 `a8c9b76c8945bbc7b19c343a5235ed00e630399a0d430853a4d7e79403f1e480`). The env file needs no change. Commit.

## 5. Deploy

- [ ] Done

```bash
# WSL, web_server with step 4 committed
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server/ansible
ansible-playbook -kK -i hosts playbook_install_webapp_find_artek.yml -v --ask-vault-pass
```

`migrate --plan` shows no migrations.

Server checks:

```bash
# SSH on sus-parcweb01
sudo docker ps --filter name=webapp-find-artek --format '{{.Names}}  {{.Image}}  {{.Status}}'      # webapp_find_artek:2026.3.1, healthy
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/find/publications/frontpage/          # 200
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/find/publications/report/add/         # 302 (to the login)
```

Rollback: put the `2026.3` entry back in `releases.yml` and rerun the playbook (no migration to reverse).

## 6. Functional checks in the browser

- [ ] Done

Reload with Ctrl+F5 first (the old `file-upload.js` may be cached).

1. (2026.3 check 4) As superuser or editor: "Add" menu → "Add report". A test report with a typed new author, an existing supervisor, a new keyword and a PDF of ~20 MB (retests FA-R12/FA-R20). Expected: the person step asks about the typed name; after "Create person" the address bar shows `.../report/add/review/` and the review shows "(new person)"; after saving the report has the PDF and a number.
2. (2026.3 check 5) Logged out: the test report is not shown (access denied) and not in the person's list. Logged in: verify it with the button, then delete it.
3. (2026.3 check 6) On the server: no new folder in `media/temp/` from this test. The folder `1795133116` (2026-11-20 00:05) is the leftover of the failed 2026.3 attempt and may be removed:
   ```bash
   sudo ls -lt /mnt/Qdrev-arctic-web-data/staticfiles/find_artek_static/media/temp/ | head -5
   sudo rm -r /mnt/Qdrev-arctic-web-data/staticfiles/find_artek_static/media/temp/1795133116
   ```
4. (2026.3 check 7) When AD shows you as a member (PowerShell: `([adsisearcher]"(&(sAMAccountName=thin)(memberOf:1.2.840.113556.1.4.1941:=CN=SUS-IT-Artek-Editor-53764,OU=SecurityGroups,OU=SUS,OU=DTUBasen,DC=win,DC=dtu,DC=dk))").FindOne() -ne $null` prints `True`): log out and in; the admin user page (`/find/admin/auth/user/`) shows `artek_editor` among the chosen groups.
5. (2026.3 check 3, optional) A student account: group `dtu_user`, name/e-mail set; no "Add" menu; `/find/publications/report/add/` → 403.

## 7. After the deploy

- [ ] Done

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
git branch -f main 2026.3.1
```

Tell the main session; it closes PLAN_registration (roadmap, archive) together with USER_STEPS_2026.3 and this file.
