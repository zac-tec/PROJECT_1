# NEO BRICKS migration status — 30 September 2026

## Current state

**Migration complete. The new VPS is the sole production writer. Both domains now point to it on authoritative DNS; the old VPS forwards cached traffic during propagation.**

- New server: `neo-admin@187.126.116.149`. Key-only SSH and passwordless sudo verified. Root SSH disabled. Hostinger console remains the recovery route.
- Old server: `neo-admin@187.53.135.144`. `brickfactory.service` stopped and disabled. Source backup cron disabled. Do NOT restart its stale database-backed app.
- Both app and company website are operational through the old server's HTTPS forwarding to the new server. TLS verification remains enabled with verification depth 3 and session reuse disabled across the different hostnames.
- Public hosts: `neobricks.online`, `neobrickskerala.com`, `www.neobrickskerala.com`.
- User approved cutover. Source entries frozen at **2026-09-30 22:59:27 IST**. Final snapshot restored; every public table's sorted-row SHA256 and row count matched before opening target traffic.
- Snapshot contained 17 sales, billed total ₹631,486. This is a cutover snapshot, not a permanent current balance.
- App baseline: `0a1d0e2` plus scheduler guard from `82f7fb0`. No historical imports or opening-balance resets performed.
- Authenticated sales retrieval, live ₹22,876 price example, app health and all three public HTTPS hosts passed.
- Current migration session complete; no server operation remains running. Another session may resume maintenance after reading this checkpoint.

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
- Cloud backup uploaded, downloaded back byte-for-byte, and fully restored to a temporary database successfully. Temporary verification database removed.
- Certbot dry-run succeeded for both production certificates, including www.
- Private configuration backup also downloaded to local `work/migration/new-vps-config-20260930.tar.gz`, mode 600.

## DNS instructions and remaining steps

Verified on authoritative nameservers (`helios` for the app; `nova` and `cosmos` for the company domain):

| Zone | Type / name | Target |
|---|---|---|
| neobricks.online | A / @ | 187.126.116.149 |
| neobrickskerala.com | A / @ | 187.126.116.149 |
| neobrickskerala.com | existing CNAME / www | keep pointing to neobrickskerala.com |

If www is an A record instead, point it to the new IP. TTL300 if available. Preserve mail/TXT/NS records. Public resolver checks found no actual AAAA record; local DNS64 synthesis is not a DNS-zone AAAA record and must not be treated as one.

1. Keep old forwarding server running for at least 48 hours while resolver caches expire; app TTL was 14,400 seconds and company TTL3,600 at verification. Retain backups for the agreed rollback window.
2. Client reviews normal app/website workflows. No real email/push test was sent; settings and secrets were preserved. Client ownership of backup/email accounts and domain renewal still needs a separate handover if currently developer-owned.
3. Retire old forwarding and securely remove client data/secrets only after explicit retirement coordination. No automatic shutdown is scheduled.

## Rollback

New production writes may now exist on target. NEVER simply re-enable the old app or redirect traffic to its stale database. Freeze target writes, back up current target data, and synchronize it into a compatible rollback environment or fix forward. The source final dump is a historical recovery point only.

## 1 October 2026 — app subdomain transition

- `app.neobrickskerala.com` configured with its own Let's Encrypt certificate alongside `neobricks.online`, serving the same frontend/backend/database.
- Both origins allowed in CORS. VAPID contact subject updated to the new app address; signing keys and existing subscriptions retained.
- Existing users/accounts/data unchanged. New-origin PWA requires separate installation/login and push enrollment. Old address remains available.
- User reports Resend domain verified; public DKIM and return-path records exist for `mail.neobrickskerala.com`.
- Existing email sender/API key remain active. Replacement key has NOT been installed or tested.
- Secure key-entry helper installed: `sudo /usr/local/sbin/neo-stage-resend-key`. Reads a hidden key interactively and writes root-only `/root/migration/resend-key.pending`; does not activate it or send email.
- Next: user privately stages a replacement key (not the one previously disclosed in chat) and specifies an authorized test recipient; then verify and switch sender to the verified mail subdomain.

## 1 October 2026 — Resend transition completed

- One authorized test sent to sachusaji675@gmail.com from `NEO BRICKS <reports@mail.neobrickskerala.com>` using the privately staged replacement key.
- Resend reported `delivered` for message `01a0f3b3-5387-7548-b639-3a69f4c1ae50` (provider delivery confirmation, not confirmation of inbox placement).
- Production `RESEND_API_KEY` and `RESEND_FROM_EMAIL` switched to the new account and sender. App restarted successfully; both app addresses remain healthy.
- Prior configuration preserved root-only at `/root/migration/app-subdomain-20261001/env.before-resend-switch`; pending key file removed. Old private backup archives still contain prior credentials and must be protected.
- No customer report recipient, report schedule, business record, or PWA signing key changed.
- Old Resend key/account can be retired separately after confirming it is not used elsewhere. No key was revoked by this operation.
