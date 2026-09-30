# NEO BRICKS migration handover

Updated: 24 September 2026. Use this file to resume the migration from another coding session/account.

## Current decision and status

- Migration is waiting for the client's new Hostinger VPS details and access.
- Default approach: reproduce the current Python/systemd + PostgreSQL + Nginx/Certbot setup. Docker was discussed but has NOT been implemented or selected as a prerequisite.
- Move the company website and management app together, retaining their existing domains initially.
- Do not make changes to production just because this handover file is opened. Inspect the checkpoint and the user's current instructions first.
- No new VPS has been provisioned, no DNS cutover has been performed, and no server connection was verified while preparing this handover.
- Local repository checked on 24 September: clean; HEAD `0a1d0e2`. Fetch and check remote history before starting; this local check does not prove remote or production has not changed.

This file supersedes Docker-first wording and the old commit baseline in the companion migration README. That README still provides the dependency inventory, cutover and rollback checklist.

## Access needed in either working environment

Use your own authorized access to each service. Signing into a different coding account does not itself supply GitHub credentials or VPS SSH access. Verify access in each environment; never assume conversation history or permissions are shared.

| Service | Known details | Required access |
|---|---|---|
| Source repository | https://github.com/zac-tec/PROJECT_1 | Git read/write through an authorized GitHub identity |
| Source branch | `main` | Fetch and inspect before edits |
| Current VPS | `187.53.135.144` | SSH as `neo-admin`, with appropriate sudo access |
| New VPS | NOT PROVIDED | IP, SSH username, authorized public key; OS/resources |
| App domain | `neobricks.online` | DNS record editing at current DNS provider |
| Company domain | `neobrickskerala.com`, existing www | DNS record editing at current DNS provider |
| Client Hostinger account | NOT PROVIDED | Client retains billing, recovery and ownership |
| Email | Resend | Client-controlled access and sending-domain configuration |
| Backups | rclone / Google Drive | Client-controlled backup destination and authorization |

Recommended SSH aliases for the operator's local SSH config (replace placeholders; these entries have not been installed):

```sshconfig
Host neo-old
    HostName 187.53.135.144
    User neo-admin
    IdentityFile ~/.ssh/REPLACE_WITH_AUTHORIZED_KEY
    IdentitiesOnly yes

Host neo-new
    HostName REPLACE_WITH_NEW_VPS_IP
    User REPLACE_WITH_NEW_SSH_USER
    IdentityFile ~/.ssh/REPLACE_WITH_AUTHORIZED_KEY
    IdentitiesOnly yes
```

On a separate computer or execution environment, generate its own key pair and authorize its PUBLIC key on the servers. Verify server fingerprints against a trusted source. Keep private keys, passwords, tokens and `.env` files out of Git and handover messages. SSH configuration alone does not establish access.

## Source code and last deployed release

Local checkout used previously:
`/Users/sachusamuel/Documents/Codex/2026-09-07/can-x20/work/repo-audit`

This path is machine-specific. Elsewhere, clone the repository into a suitable workspace.

Last recorded deployed/pushed release:
`0a1d0e2` — Support live pre-GST brick and delivered sale pricing.

Key recent changes:
- Manager date selection with shared admin-controlled backdating allowance.
- Mobile layout improvements and animated login opening.
- Two live pre-GST sales methods: brick price plus transport, or agreed delivered price including transport.
- Reference invoice: 2,500 × ₹8.17 = ₹20,425 before GST; driver ₹2,200; brick value ₹18,225; GST ₹2,451; total ₹22,876.
- Explicit driver base amounts excluded from profit revenue; legacy sales unchanged until edited.
- Latest schema migration: `brickfactory/migration_sale_pricing.sql`.
- Feature details: `brickfactory/SALE_PRICING.md`.

Do not rebuild from the September 15 README or an older commit. Do not reimport historical sales, reset opening stock or rerun a starter schema over production data.

## Existing production inventory

Recorded during earlier work; refresh before migration:

- App directory: `/home/vps/apps/brickfactory`
- App owner: `vps`
- Service: `brickfactory.service`
- Virtual environment: `/home/vps/apps/brickfactory/venv`
- Python 3.12 observed; capture actual installed dependency versions.
- API: `127.0.0.1:8000`
- App frontend: `/home/vps/apps/brickfactory/frontend`
- Company static site: `/var/www/neobrickskerala`
- Website source/build: `website/` in repository, React/TypeScript/Vite; verify compatible Node and lockfile.
- PostgreSQL database: `brickfactory`; application role: `brickapp`.
- PostgreSQL major version: must be checked before selecting target version.
- Nginx domain-specific configurations and Let's Encrypt certificates, with Certbot renewal timer.
- `/health` checks API liveness only; separately verify database access.
- Live application directory has no dependable Git history. Compare deployed files to the selected release before replacing anything.

Additional test/preview hostnames were present. Do not move them as client production unless the user includes them in scope.

## Private configuration and external services

Transfer securely, never through this file:

- Database credentials and any `DATABASE_URL` override.
- JWT signing secret and user/session-version data.
- Resend key; recorded sender `onboard@neobricks.online`.
- CORS allowed origin `https://neobricks.online`.
- VAPID public/private key pair and push subscription tables.
- Recorded private-key location: `/home/vps/.config/brickfactory/vapid-private.pem`.
- TLS material, renewal setup and account contact details.
- Any runtime uploads/files found during inventory.
- rclone authorization and client-owned backup destination.

Keep domains unchanged for the initial migration. A registrar transfer lock does not normally prevent updating hosting address records; confirm DNS access. Changing DNS hosting destination is separate from transferring domain ownership. Preserve email-related and unrelated DNS records.

## Scheduled jobs and backup dependencies

The app starts APScheduler inside the backend process. Do not run two production schedulers. A general scheduler-disable flag was NOT implemented during the pricing work: inspect current source and implement/test isolation if necessary before starting a second copy.

A rehearsal instance must not send real report emails or push notifications. Use isolated credentials and disable scheduled delivery. Keep Asia/Kolkata timezone and verify report trigger times.

Recorded backup setup:
- `/usr/local/sbin/brickfactory-backup`
- `/etc/cron.d/brickfactory-backup`
- Sunday 02:00 server time (IST observed)
- `/var/backups/brickfactory`
- `/home/vps/.config/rclone/rclone.conf`
- `gdrive:brickfactory-backups/hostinger`

New pricing-release backups were created under `/var/backups/brickfactory/pricing-20260922/`, including `deployment.dump` and `code/`. They are rollback snapshots for that release, not a current migration snapshot. Take a fresh backup when migrating.

Verify offsite upload and a restore. Copying the developer's Google token does not transfer backup ownership to the client.

## Working across two accounts/sessions

Use sequential handoffs. Only ONE session may change a server, restore a database or modify DNS at a time. A low-credit pause must not leave another session assuming it should repeat an operation.

Keep these non-secret files in the repository when migration implementation begins:

- `docs/migration/HANDOVER.md`: this context and decisions.
- `docs/migration/STATUS.md`: current phase, active operator, exact last completed operation and next step.
- `docs/migration/RUNBOOK.md`: the actual commands/configuration for the chosen architecture.

These repository files have not been created or pushed by preparing this standalone handover. Copy the reviewed documents into the repository at the start of migration and commit them.

At each handoff:
1. Stop starting new mutations; determine whether the current operation completed or is still running.
2. Record server hostname, release commit, backup location, database state, service state and any failed command. Include no secrets or customer data.
3. Commit and push completed source/configuration work and the checkpoint. Record uncommitted work explicitly if a commit is not yet appropriate.
4. Mark the session paused and release the operator lock in STATUS.md.
5. In the next session, fetch Git, inspect local changes and read STATUS.md before proceeding. Do not blindly pull over local edits.
6. Verify the recorded state with focused read-only checks. Resume from the first incomplete step.

Checkpoints should distinguish “command started”, “command completed” and “result verified”. Never mark a phase complete just because a tool was called.

## Checkpoint template

```text
Updated at (include timezone):
Active operator/session:
Status: waiting / running / paused / completed
Chosen architecture: existing systemd stack (unless user changes decision)
Source VPS:
Target VPS:
Repository branch and commit:
Last completed and verified step:
Operation still running, if any:
Source accepting writes? yes/no
Target accepting writes? yes/no
Active production scheduler location:
Latest verified backup path and timestamp:
Restore verified? where/how:
DNS currently points to:
Changes not committed/pushed:
Failure/blocker:
Exact next step:
Rollback available and limitations:
```

Never allow source and target to accept independent production writes simultaneously.

## Migration phases

1. **Access and inventory:** confirm new VPS, OS/resources, SSH, Git and DNS access. Refresh source versions/configuration and capture a reproducible dependency list.
2. **Target preparation:** install compatible Python/PostgreSQL/Nginx/Certbot and configure services. Match current architecture; no unrequested major version upgrades.
3. **Isolated rehearsal:** restore a fresh source dump, isolate notifications/schedulers, verify app and company website under their intended hostnames. Check key counts/totals, login, sales preview, ledger, stock and TLS. Keep tests focused.
4. **Cutover preparation:** save DNS records/TTLs, arrange maintenance window, ready certificates, verify rollback and client-owned backups. Finish this phase before starting a session likely to run out of available usage.
5. **Final synchronization:** block source writes and stop its scheduler, take a fresh final dump, transfer/restore final data and mutable files, verify target. No reopening stale source writes.
6. **Traffic switch:** update relevant A/AAAA/www records, retain source maintenance or deliberately proxy to the target during propagation. Enable exactly one production scheduler.
7. **Acceptance:** check both public sites, database-backed workflows, agreed email/push tests, certificate renewal and backup restore.
8. **Handover:** client controls billing/recovery. Retain rollback material for the agreed period, then remove client secrets/data before using the old VPS for other projects.

Before new target writes, rollback may return to the unchanged source. After new target writes, do not restart the stale source database: freeze writes and synchronize current data into a compatible rollback environment or fix forward.

## Prompt to paste into the next session

> Continue the NEO BRICKS VPS migration. Read MIGRATION_HANDOVER.md and the latest repository migration STATUS.md first. Use the existing Python/systemd, PostgreSQL, Nginx and Certbot architecture unless I explicitly choose Docker. The last recorded deployed release is 0a1d0e2, but refresh Git and compare live files before changing anything. Keep neobricks.online and neobrickskerala.com unchanged. Preserve all business data, pre-GST pricing, customer accounts, email, push and backups. Never run two production writers or schedulers. First report the current checkpoint and missing access, then continue authorized preparation. Update and push the non-secret migration checkpoint after each phase so another session can resume. Keep checks focused; I will manually review the UI.

## Information still needed from the user

- Has the client-owned VPS been purchased?
- New VPS IP, operating system and SSH username.
- Which machine/environment will each coding session use?
- Confirmation that the public SSH keys are authorized and GitHub access works.
- Who can edit DNS for each domain and when the maintenance window can occur.

Provide credentials only through secure authentication mechanisms, not by adding them to this document.
