# Migration status — 30 September 2026, approximately 23:00 IST

Active operator: this migration session. Do not run simultaneous server changes.

- Source: `neo-admin@187.53.135.144`, still production.
- Target: `neo-admin@187.126.116.149`, key-only sudo access verified. Root SSH/password authentication disabled.
- Target restored initial database/configuration backup. Compatible Python 3.12 and PostgreSQL 16; matching source Python package versions.
- Deployed baseline `0a1d0e2`; 115 source files compared. Differences only in old task notes and test-file placement. Application code matches.
- New scheduler environment guard added, default enabled. Target rehearsal has `ENABLE_SCHEDULER=false` and systemd outbound network restriction to localhost.
- Nginx temporarily denies external requests on target; internal HTTPS checks passed for app and company website.
- Authenticated preview and database sales retrieval verified. Actual bill example is ₹22,876.
- Initial backup: `/var/backups/brickfactory/migration-20260930-initial/` on source; private local archive and target `/root/migration/source/` also hold verified copies.
- No final freeze or traffic switch yet. User approved brief entry pause and will update DNS when instructed.
- Next: freeze source, take final DB backup/fingerprints, restore and compare target, then activate target and forward old-domain traffic to target. Preserve a single writer/scheduler.
- Target UFW allows TCP22/80/443 only; database/API bind loopback. Fail2ban SSH jail and unattended upgrades enabled; package upgrades complete, no reboot required.
- Backups will use existing Google Drive credentials under separate `brickfactory-backups/hostinger/client-vps-187126116149` destination. Client ownership of Google Drive/Resend is not yet transferred.
