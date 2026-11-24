# User steps: release 2026.8 (feature registration)

Release `2026.8` is `develop/main` after [PLAN_features](../archive/PLAN_features_COMPLETE.md) (fast-forwarded 2026-11-24 with the owner's OK, `d393f17`; plan closed in `f97bdc9`). Checks on `d393f17`: `tests/run.sh` ALL 22 TESTS PASSED, 1239 Django tests OK; the owner's browser checks in the dev stack (USER_STEPS_features, sections 1-2 and rechecks R-U).

What changes for users:

- **Features on reports:** add by coordinates (any EPSG code, help list for Greenland, original coordinates kept), draw on the map, or import from Excel (sheet "Features", preview first, template on the import page); edit coordinates or geometry; delete; "Remove from report" for a feature on several reports. Files and images on features (upload, delete; thumbnails).
- **Reports:** a report with features can't be deleted (the page says what to do); "Delete all features"; appendices can be deleted; confirm dialogs on every real delete. Superusers: "Bulk delete reports" tile on Administration.
- **Map:** EPSG:3574 (Greenland upright); Dataforsyningen topographic map (default), satellite and Sentinel-2, overlays place names, contours, UTM grid; Arctic SDI basemap outside Greenland; feature type filter and legend; list of reports in view; box-zoom button. Without the token only the Arctic SDI basemap is shown.
- **Downloads:** all media files get `X-Content-Type-Options: nosniff`; only PDF, TXT, PNG, JPEG, GIF and WebP open in the browser, everything else downloads (also appendices such as docx/xlsx/zip/csv).

Deployment impact (web_server):

- **New env variable `FA_DATAFORSYNINGEN_TOKEN`** in `webapp_find_artek.env` (step 6). Empty or missing = the app works, the map shows only the Arctic SDI basemap. The token is rendered into the map pages (web-map token, visible in the page source), so use a token meant for this site.
- **Migration `0006_feature_source_and_observation_date`:** adds four empty columns to `publications_feature` (`observation_date`, `source_geometry`, `source_srid`, `transform_note` default `''`). No existing row changes. Reversible (`migrate publications 0005`). The playbook's `migrate --plan`/`migrate` applies it.
- **Visitors' browsers** load map tiles from `api.dataforsyningen.dk` and `basemap.arctic-sdi.org` (no server change; matters for a later CSP, FA-R31). The map scripts (Leaflet, proj4) are served from `/find/static/`.
- **Optional nginx header** (step 7): nginx probably drops the app's `X-Content-Type-Options` on `X-Accel-Redirect` responses. Downloads are safe without it (octet-stream + attachment); it matters only for the inline types.
- Static scripts load as `...?v=2026.8-t23` (`STATIC_ASSET_VERSION`). Port, paths, user, entrypoint, cron and the `tests/run.sh` interface unchanged.

## 1. Fast-forward `develop/main` (main session, with your OK)

- [x] Done (2026-11-24: `develop/main` = `d393f17`, then docs `f97bdc9`).

## 2. Tag `2026.8` (main session, with your OK)

- [x] Done (2026-11-24, main session: annotated tag `2026.8` on `f97bdc9`, local only). **Push it yourself:**

```powershell
# PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
git push origin develop/main 2026.8
```

## 3. Build and test the bundle (main session)

- [x] Done (2026-11-24, main session: `RESULT: OK, bundle written, tests passed`, 22/22, `Ran 1239 tests` OK; tarball_sha256 `0e094359c1ff6b48afd050a55100c58542bef02883b5b4ec0160c1588cc18030`, image_id `sha256:06aa84fbaffd...`, git_sha `f97bdc996263`).

```bash
# WSL
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server
bash scripts/build_image.sh webapp_find_artek /mnt/c/thin/02_Code/docker_projects/find_artek_DEVELOP 2026.8
cat release-out/webapp_find_artek/webapp_find_artek-2026.8.manifest.txt
```

## 4. Publish to the releases share (main session)

- [x] Done (2026-11-24, main session: the three files copied, hash on the share = manifest).

```powershell
# PowerShell
$dst = '\\ait-pdfs\Qdrev\SUS\Groups\Arctic_backup\SUS-PArcWeb01\releases\webapp_find_artek'
Copy-Item 'C:\thin\02_Code\docker_projects\dtu_sus_web_server\release-out\webapp_find_artek\webapp_find_artek-2026.8.*' $dst
Get-FileHash -Algorithm SHA256 "$dst\webapp_find_artek-2026.8.tar.gz"   # = tarball_sha256 in the manifest
```

## 5. releases.yml (main session)

- [x] Done (2026-11-24, main session: web_server `develop/main` commit `a855341`, 2026.7 kept commented out; not pushed, see 10b).

`ansible/vars/releases.yml` in web_server: `version: "2026.8"`, `tarball_sha256` from the manifest, 2026.7 kept commented out for rollback; committed on web_server's `develop/main`, not pushed.

## 6. Add the token to the secrets (you)

The token goes into the env file of the find_artek containers, which lives in web_server's encrypted secrets archive (`docker/secrets.tar.gz.vault`). Agents never see it.

1. Get a token for production on dataforsyningen.dk (log in, "Mine tokens"). Prefer a new one over the dev token, which was shown once in an agent's output during PLAN_features.
2. Edit the plaintext copy outside the repository: item `docker/secrets/webapp_find_artek.env` in your secrets folder (web_server `docs/deploy/secrets.md`, "Where the plaintext lives"). Add one line (no quotes, no spaces):

   ```
   FA_DATAFORSYNINGEN_TOKEN=<your token>
   ```

3. Encrypt only that item and commit the vault file:

   ```bash
   # WSL
   cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server
   bash scripts/vault_secrets.sh encrypt docker/secrets      # asks for the vault password twice
   git add docker/secrets.tar.gz.vault
   git commit -m "find_artek: FA_DATAFORSYNINGEN_TOKEN in webapp_find_artek.env"
   ```

The find_artek playbook imports `playbook_deploy_files.yml`, which unpacks the secrets on the host, so step 8 brings the token along; compose recreates the containers because the env file changed.

## 7. Optional: nginx `nosniff` on protected media (you)

In `C:\thin\02_Code\docker_projects\dtu_sus_web_server\docker\services\nginx\nginx.conf`, in `location /find/_protected_media/` (around line 236), add a line after `alias ...;`:

```nginx
            add_header X-Content-Type-Options nosniff always;
```

Commit, then deploy nginx (before or after step 8):

```bash
# WSL
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server/ansible
ansible-playbook -kK -i hosts playbook_install_nginx.yml -v --ask-vault-pass
```

Check: in DevTools, Network tab, the response of a report PDF has `X-Content-Type-Options: nosniff`. Tell the main session if you want it to make the edit instead.

## 8. Deploy the app (you)

```bash
# WSL
cd /mnt/c/thin/02_Code/docker_projects/dtu_sus_web_server/ansible
ansible-playbook -kK -i hosts playbook_install_webapp_find_artek.yml -v --ask-vault-pass
```

The playbook takes the pre-deploy dump and runs `migrate --plan` (expect only `publications.0006_feature_source_and_observation_date`) and `migrate`.

Server checks:

```bash
# SSH on sus-parcweb01
sudo docker ps --filter name=webapp-find-artek --format '{{.Names}}  {{.Image}}  {{.Status}}'      # webapp_find_artek:2026.8, healthy
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/find/publications/frontpage/          # 200
sudo docker exec webapp-find-artek python manage.py showmigrations publications | tail -1          # [X] 0006_feature_source_and_observation_date
sudo docker logs --since 10m webapp-find-artek 2>&1 | grep -iE 'traceback|error' | head            # nothing
```

Rollback: put the `2026.7` entry back in `releases.yml`, then `sudo docker exec webapp-find-artek python manage.py migrate publications 0005` **before** rerunning the playbook (2026.7 doesn't know 0006), or restore the pre-deploy dump.

## 9. Functional checks in production (you)

Ctrl+F5 first, on `https://arctic.sustain.dtu.dk/find/`:

1. Logged out: front page, report list and the map load. The map shows the **topographic map** (the token works; without it only the Arctic SDI basemap and "More map layers need FA_DATAFORSYNINGEN_TOKEN" in the corner). Type filter, legend, reports in view and box zoom work.
2. A confidential report's PDF: opens logged in, refused logged out; a public report's PDF opens logged out.
3. Log in through CAS. Create a test report `ZZ release check (delete me)`, unvalidated: add a feature by coordinates and one on the map, upload a small image to one of them, then delete both features and the test report.
4. `/find/api/report/` returns JSON; `/find/swagger/` loads.
5. Next morning: thumbnail cron as before (`sudo docker logs --since 24h webapp-find-artek 2>&1 | grep -F '[thumbnails]' | tail -4`).

## 10. After closing (you)

- [ ] a. Fast-forward `main` to the deployed tag (FA5) and push it:

  ```powershell
  # PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
  git merge-base --is-ancestor main 2026.8; if ($?) { git branch -f main 2026.8 }
  git push origin main
  ```

- [ ] b. Push web_server `develop/main` (releases.yml, the vault file, nginx if step 7):

  ```powershell
  # PowerShell, in C:\thin\02_Code\docker_projects\dtu_sus_web_server
  git push github develop/main
  ```

- [ ] c. Give the dev stack back to your checkout and remove the feature worktree (the stack runs from `..\find_artek_agent-features` since 2026-11-23; the dev database volume is kept):

  ```powershell
  # PowerShell, in C:\thin\02_Code\docker_projects\find_artek_agent-features
  docker compose -f docker-compose.yml -f docker-compose.develop.yml down
  # PowerShell, in C:\thin\02_Code\docker_projects\find_artek_DEVELOP
  docker compose -f docker-compose.yml -f docker-compose.develop.yml up -d --build
  git worktree remove ..\find_artek_agent-features    # if it refuses because of the copied .dev.env: add --force
  git branch -d agent-features                         # merged into develop/main
  ```

Tell the main session when steps 8-10 are done; it archives this file.
