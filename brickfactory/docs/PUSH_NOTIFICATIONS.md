# Production reminders

On both installed phones, sign in and open **Settings → Enable notifications → Allow**. Enable each device separately. Closing the app is fine; signing out disables notifications on that device. On iPhone use the installed Home Screen app.

All times are Asia/Kolkata, Monday–Saturday:

| Time | Recipient | Condition |
| --- | --- | --- |
| 20:00 | Manager | No production record for today |
| 22:00 | Manager and admin | Still no production record for today |

No Sunday reminders and no scheduled reminders after 22:00. Sales remain available every day. A saved production row, including a zero-production day, counts as submitted. Saving sales alone does not count as production submission.

Two APScheduler jobs run in the existing app process. Delivery claims are persisted in PostgreSQL to suppress duplicates. Credential rotation invalidates subscriptions tied to the previous session version. Expired provider subscriptions are deleted. Push delivery depends on phone permission, connectivity and OS settings; provider acceptance does not prove the phone displayed a notification. Delivery TTL is 60 seconds. Failed attempts are logged, without subscription secrets, and are not automatically retried that slot. Missed schedules during server downtime are not replayed.

## Deployment and recovery

Install `requirements.txt`; startup applies `migration_push_notifications.sql`.
Configure privately in `.env`:

```
VAPID_PRIVATE_KEY_FILE=/secure/path/vapid-private.pem
VAPID_PUBLIC_KEY=<base64url uncompressed P-256 public key>
VAPID_SUBJECT=https://neobricks.online
```

Keep the private EC P-256 key, environment configuration and database backup in secure recovery storage, never the public repository. Restoring the same key and subscription database preserves subscriptions; replacing the key requires devices to unsubscribe and enable again. Current server key location: `/home/vps/.config/brickfactory/vapid-private.pem` (mode 600). Inclusion of this newly created key in off-server backups must be checked separately.

Run `python -m unittest discover -s tests -p test_push_reminders.py -v`. These tests do not send real notifications.
