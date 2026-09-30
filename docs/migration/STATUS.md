# NEO BRICKS migration status — 30 September 2026

## Current state

**The new VPS is the sole production writer. The old VPS only forwards the production domains. DNS updates are pending user confirmation.**

- New server: `neo-admin@187.126.116.149`. Key-only SSH and passwordless sudo verified. Root SSH disabled. Hostinger console remains the recovery route.
- Old server: `neo-admin@187.53.135.144`. `brickfactory.service` stopped and disabled. Source backup cron disabled. Do NOT restart its stale database-backed app.
- Both app and company website are operational through the old server's HTTPS forwarding to the new server. TLS verification remains enabled with verification depth 3 and session reuse disabled across the different hostnames.
- Public hosts: `neobricks.online`, `neobrickskerala.com`, `www.neobrickskerala.com`.
- User approved cutover. Source entries frozen at **2026-09-30 22:59:27 IST**. Final snapshot restored; every public table's sorted-row SHA256 and row count matched before opening target traffic.
- Snapshot contained 17 sales, billed total ₹631,486. This is a cutover snapshot, not a permanent current balance.
- App baseline: `0a1d0e2` plus scheduler guard from `82f7fb0`. No historical imports or opening-balance resets performed.
- Authenticated sales retrieval, live ₹22,876 price example, app health and all three public HTTPS hosts passed.
- Current operator is still finalizing backup/certificate verification and DNS. Other sessions must read the latest checkpoint before making changes.

## Configuration

Existing layout preserved: app `/home/vps/apps/brickfactory`, company website `/var/www/neobrickskerala`, Python virtualenv inside app, PostgreSQL 16 database `brickfactory`, role `brickapp`, Nginx and Certbot. All source Python package versions reproduced in target `requirements-production.lock`.

- App/API and PostgreSQL listen on localhost only.
- UFW allows inbound TCP22/80/443, including IPv6; other inbound traffic denied.
- Fail2ban SSH protection active; root/password/keyboard-interactive SSH disabled.
- Security/package updates applied; unattended upgrades enabled, automatic reboot disabled. No reboot was required.
- App systemd hardening: NoNewPrivileges, PrivateTmp, ProtectSystem=full, ProtectHome=read-only, UMask=0077.
- Asia/Kolkata timezone preserved. One production scheduler runs on target; configured daily email time is 19:00 IST. Source scheduler is stopped.
- Rehearsal restrictions were removed after final restore. `ENABLE_SCHEDULER=false` is now available for future isolated rehearsals; defaults to enabled in production.
- VAPID keys, JWT secret, Resend sender/key and subscription data preserved. No test email or push notification has been sent to customers.

## Backups and scheduled work

- Initial source backup: `/var/backups/brickfactory/migration-20260930-initial/`.
- Final source backup: `/var/backups/brickfactory/migration-20260930-final/` (database, fingerprints, source Nginx and disabled cron/renewal configurations).
- Target final snapshot: `/root/migration/migration-20260930-final/`.
- Private local task copies: `work/migration/source-backup-20260930.tar.gz` and `work/migration/final-backup.tar.gz`, mode 600. Never commit archives, secrets, dumps or credentials.
- Target backup script `/usr/local/sbin/brickfactory-backup`; weekly Sunday02:00 IST cron `/etc/cron.d/brickfactory-backup`.
- Google Drive destination: `gdrive:brickfactory-backups/hostinger/client-vps-187126116149`, using the EXISTING rclone account. This migration does not transfer Google Drive or Resend account ownership/billing.
- New target configuration archive: `/root/migration/new-vps-config-20260930.tar.gz` (private).
- Certbot renewal timer enabled on target for the two production certificates. Old renewal entries for these two domains parked with source final backup; preview/test renewals remain separate.
- Cloud backup restore and renewal dry-run: verification running at this checkpoint; update result before claiming complete.

## DNS instructions and remaining steps

User has been asked to update:

| Zone | Type / name | Target |
|---|---|---|
| neobricks.online | A / @ | 187.126.116.149 |
| neobrickskerala.com | A / @ | 187.126.116.149 |
| neobrickskerala.com | existing CNAME / www | keep pointing to neobrickskerala.com |

If www is an A record instead, point it to the new IP. TTL300 if available. Preserve mail/TXT/NS records. Public resolver checks found no actual AAAA record; local DNS64 synthesis is not a DNS-zone AAAA record and must not be treated as one.

1. Finish offsite restore and certificate renewal verification.
2. Verify user DNS edits on authoritative servers and public resolvers.
3. Retain old forwarding server through propagation and agreed rollback window. Do not cancel it immediately after DNS change.
4. Client reviews normal app/website workflows. Client ownership of backup/email accounts and domain renewal still needs a separate handover if currently developer-owned.
5. Retire old forwarding and securely remove client data/secrets only after explicit retirement coordination.

## Rollback

New production writes may now exist on target. NEVER simply re-enable the old app or redirect traffic to its stale database. Freeze target writes, back up current target data, and synchronize it into a compatible rollback environment or fix forward. The source final dump is a historical recovery point only.
