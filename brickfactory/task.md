# NEO BRICKS — remaining tasks

## Working rules

- The app currently runs on the **Raspberry Pi**, through the existing Tailscale/Magic DNS HTTPS address. The SSH alias `vps` points to this Pi; it is not a purchased commercial VPS.
- Commercial VPS purchase/migration is planned within two days. HTTPS already works on the Pi; the new VPS will need its own setup and verification.
- Do **one small task at a time**. Keep changes and tests focused; reuse existing tests. No broad refactors or infrastructure upgrades now.
- Before editing, add the agent's scope under “In progress” and check for another agent's claim. Preserve live data and unrelated changes. Remove completed tasks from this list.
- Never put secret values in this file. Never run legacy `schema.sql` on live data.

## In progress





- Database setup verification: document fresh/restore paths, enforce migration order, and add an isolated temporary-database test.

## Repository reset

- 2026-09-06: Fresh Git contents cleaned: old Git metadata moved outside `apps`; retired browser scripts are ignored but retained locally; active scripts documented. Secrets, virtualenv, caches and archives remain excluded. No files staged or pushed by this cleanup.

- 2026-09-06: Local Git was reinitialized before recreating the remote repository. The previous `.git` metadata was moved outside the repository into a private `repo-preparation-*` directory under `/home/vps/app-update-backups/`. No files have been staged or pushed.
- 2026-09-06: `.env.example` was redacted to placeholders. The live `.env` remains local and ignored.

## On the Pi / before moving

- [ ] **Urgent: rotate exposed secrets.** Current DB password, JWT secret and Resend API key matched a remote-tracking Git snapshot. Untracking `.env` did not revoke them. Coordinate database/JWT rotation with service restart; obtain and revoke the email key through the provider. Do not carry these old secrets to the VPS.
- [ ] **Fix the fresh-install schema/auth mismatch.** Use `password_hash` and safe account setup; keep the live database untouched.
- [ ] **Prepare the migration steps.** Identify the required SQL files and their order, and check the restore path in an isolated database. Keep this practical; a new migration framework is not required now.
- [ ] **Review the Git cleanup.** Confirm the other agent's changes before committing. Do not bundle unrelated edits or push secrets/history accidentally.
- [ ] **Confirm remaining feature ownership with the other agent:** customer payments, sales date filters/pagination and clearer profit estimates. Work on only one feature after it is claimed here.

## When the VPS is bought — before switching users to it

- [ ] Set up the application, database, environment and service using fresh secrets.
- [ ] Configure the chosen domain/access method, HTTPS, Nginx routing and the allowed CORS origin for the new address.
- [ ] Back up the Pi and restore onto the VPS. Verify the latest business records before switching; keep the Pi copy for rollback.
- [ ] Run existing focused tests and smoke-check login, both roles, production, sales, stock and reports on the VPS. Check permissions and blocked unauthenticated access.
- [ ] Verify scheduled email settings, timezone and a controlled delivery test; avoid running duplicate report senders on Pi and VPS.
- [ ] Configure automatic backups and verify a restore. Record the deployed version and final start/restart instructions.

## Later — only when needed

- [ ] Safely retire old frontend script variants after checking cached-page compatibility.
- [ ] Add deeper FIFO/sale-edit/stock-adjustment/production-correction tests alongside relevant changes; no large test-suite expansion now.
- [ ] Consider connection pooling only if connection load becomes a problem.
- [ ] Consider a separate report scheduler only if API downtime affects delivery.

Completed frontend recovery/security changes and the verified Pi backend/Git-tracking cleanup have been removed from this task list. Historical details and backups remain available; secret rotation and the review/commit step are still outstanding.

Database setup documentation, an ordered runner, and the isolated test have been added. The test still requires a PostgreSQL role with permission to create/use a disposable database; it has not touched the live Pi database.

## UI merge status — 2026-09-07

`ui-redesign` was already merged into `main` at `db18bce`. Integration removes demo API code/references, preserves recovery/security behavior, maps old admin sections into Pricing/Orders, and adds a dialog-close fallback. Asset/cache version is `ui-live1`. Focused recovery, stored-XSS, navigation/asset and integration tests passed without live business writes. Current branch and uncommitted frontend were backed up in `/home/vps/app-update-backups/ui-merge-20260907-011606` and branch `backup/ui-merge-20260907-011606`. The redesign worktree is retained. No push performed by this agent.

Manager UI adjustment — 2026-09-07: navbar uses six equal columns; small labels/body notes/buttons/tables use 15px, inputs remain 16px. Manager-only styling; no business logic changed. Backup: /home/vps/app-update-backups/manager-spacing-20260907-012448.

2026-09-07: PWA updated to NEO BRICKS, fullscreen with standalone fallback, monochrome NB icons, Apple home-screen metadata, and cache version pwa-nb2. Installed launch required; OS fullscreen support varies.

2026-09-07: Reporting emails now use NEO BRICKS branding, readable dates, plain-text/HTML bodies and branded PDF filenames. PDF report labels updated. Delivery recipient and schedule remain private database settings, editable in the app.

2026-09-07: Admin dashboard active-users panel added. Visible authenticated apps signal every minute; unique accounts expire after five minutes. Single-worker in-memory presence clears on restart. Tests cover authentication, admin access, deduplication, cache prevention and expiry.
