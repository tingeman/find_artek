# User steps: Release path and pinning (Phase 1)

Plan: [PLAN_release-path.md](PLAN_release-path.md). Status: [STATUS_release-path.md](STATUS_release-path.md).

Steps only you can run (host access, decisions, merges, tags). Everything here is read-only on the host unless a step says otherwise. Paste the output of each read-only step back into the session (or into `docs/plan/BASELINE_release-path.md`), so the next tasks can use it.

### 1. Settle the open points of the dev-database guide

- [ ] Done

Where: in the session. Answer P1–P7 at the end of [`docs/quick-guides/01_sync_dev_db_from_prod.md`](../quick-guides/01_sync_dev_db_from_prod.md) (SSH user and sudo, variable names, transport, local folder, dev DB user, media, login). The orchestrator then finalises the guide.

### 2. Host baseline (T0)

- [ ] Done

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

- [ ] Done

Where: SSH on the host and PowerShell on the workstation, as the guide says. After step 1 is settled, follow [`docs/quick-guides/01_sync_dev_db_from_prod.md`](../quick-guides/01_sync_dev_db_from_prod.md). Its step 2 can run in the same SSH session as step 2 above. Not needed for the automated checks (they use a throwaway database), but for manual testing with real data.

### 4. Later: merge, tag and release (T8, T9)

- [ ] Done

Not yet. When T1–T7 are done and reviewed, the orchestrator asks you to allow the fast-forward of `develop/main` to `agent-release-path`. Then you tag `2026.1`, build it with web_server's `scripts/build_image.sh` and deploy it through web_server's M5 plan. The exact commands come with T9.
