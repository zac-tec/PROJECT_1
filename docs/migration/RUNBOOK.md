# Production operations after migration

Read STATUS.md before acting. Current server: `ssh neo-admin@187.126.116.149`, using the authorized key and sudo. Root/password SSH is disabled; use the Hostinger browser console for recovery.

## Read-only checks

```sh
sudo systemctl status brickfactory nginx postgresql fail2ban --no-pager
curl -fsS http://127.0.0.1:8000/health
sudo journalctl -u brickfactory -n 30 --no-pager
sudo ufw status
```

API health is liveness only. Verify authenticated database-backed reads for app diagnosis without creating production test sales.

## Backups

```sh
sudo /usr/local/sbin/brickfactory-backup
```

This creates a private PostgreSQL custom-format dump under `/var/backups/brickfactory` and uploads it to the existing Google Drive remote at `brickfactory-backups/hostinger/client-vps-187126116149`. Weekly cron remains Sunday02:00 IST. Read `/var/log/brickfactory-backup.log` for scheduled runs.

Restore only into an explicitly named isolated database for verification. Never restore over current production without stopping writers and taking a fresh current backup. Full restore and cloud download verification passed during migration.

Configuration recovery archives are under `/root/migration/`. They contain credentials; do not commit or expose them. Source backups and old forwarding configuration are described in STATUS.md.

## TLS

Certbot timer is active. Both production domain renewals use webroot. The deploy hook tests/reloads Nginx. Both simulated renewals passed after migration.

## Scheduler and deployment

`ENABLE_SCHEDULER=false` disables startup and rescheduling on an isolated rehearsal. Production defaults to enabled. Use one application worker/replica unless scheduler architecture is changed. Rehearsals also require isolation of outbound email/push and production writes.

Runtime dependencies are pinned in the server's `requirements-production.lock`. Code baseline is `0a1d0e2` plus scheduler guard `82f7fb0`. Compare current Git and live files before future deployments.

The old server `187.53.135.144` runs Nginx forwarding only for production hosts. Its production app and backup cron are disabled. Nginx verifies target TLS, uses depth3 and disables SSL session reuse across hostnames. Do not restart the stale old application. After any new target writes, rollback requires current target data, not the source's September30 snapshot.
