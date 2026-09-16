"""Production reminders. All reminder times are factory time (Asia/Kolkata)."""
import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
import base64
import requests

class PushSession(requests.Session):
    def request(self, method, url, **kwargs):
        kwargs["allow_redirects"] = False
        return super().request(method, url, **kwargs)

from database import get_connection

log = logging.getLogger(__name__)
IST = ZoneInfo('Asia/Kolkata')


def public_config():
    key = os.getenv('VAPID_PUBLIC_KEY', '')
    path = os.getenv('VAPID_PRIVATE_KEY_FILE', '')
    return {'enabled': bool(key and path and os.path.isfile(path)), 'public_key': key}


def validate_subscription(endpoint, p256dh, auth):
    url = urlsplit(endpoint)
    host = url.hostname or ''
    allowed = (host == 'fcm.googleapis.com' or host == 'updates.push.services.mozilla.com'
               or host.endswith('.push.apple.com') or host.endswith('.notify.windows.com'))
    if not allowed or url.scheme != 'https' or url.port not in (None, 443) or url.username or url.password or url.fragment:
        raise ValueError('Unsupported push service endpoint.')
    for value, size in ((p256dh, 65), (auth, 16)):
        decoded = base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)
        if len(decoded) != size or (size == 65 and decoded[0] != 4):
            raise ValueError('Invalid push subscription key.')


def reminder_roles(now, slot):
    local = now.astimezone(IST)
    # Permit only the scheduled minute, including after a server restart.
    if local.weekday() == 6 or slot not in (20, 22) or local.hour != slot or local.minute != 0:
        return ()
    return ('manager',) if slot == 20 else ('manager', 'admin')


def run_production_reminders(slot):
    from pywebpush import webpush, WebPushException
    now = datetime.now(IST)
    roles = reminder_roles(now, slot)
    if not roles or not public_config()['enabled']:
        return
    conn = get_connection()
    try:
        with conn.cursor() as c:
            c.execute('DELETE FROM push_deliveries WHERE reminder_date < CURRENT_DATE - 90')
            c.execute('''SELECT s.*,u.user_role FROM push_subscriptions s JOIN system_users u
                         ON u.username=s.username AND u.session_version=s.session_version
                         WHERE u.user_role=ANY(%s)''', (list(roles),))
            subscriptions = c.fetchall()
        conn.commit()
        for sub in subscriptions:
            if not reminder_roles(datetime.now(IST), slot):
                break
            with conn.cursor() as c:
                # Recheck immediately before each delivery; credential changes revoke delivery too.
                c.execute('SELECT 1 FROM production_log WHERE production_date=%s', (now.date(),))
                if c.fetchone():
                    break
                c.execute('SELECT 1 FROM system_users WHERE username=%s AND session_version=%s',
                          (sub['username'], sub['session_version']))
                if not c.fetchone():
                    continue
                c.execute('''INSERT INTO push_deliveries(subscription_id,reminder_date,slot)
                             VALUES(%s,%s,%s) ON CONFLICT DO NOTHING RETURNING subscription_id''',
                          (sub['id'], now.date(), slot))
                claimed = c.fetchone()
            conn.commit()
            if not claimed:
                continue
            role = sub['user_role']
            date = now.strftime('%d-%m-%Y')
            body = (f'Production for {date} is still missing. Please ask the manager to submit it.'
                    if role == 'admin' else f'Please submit production and working hours for {date}.')
            payload = {'title': 'NEO BRICKS — Missing production', 'body': body,
                       'url': f'/{role}.html', 'tag': f'production-{now.date()}-{slot}'}
            status = 'sent'
            try:
                validate_subscription(sub['endpoint'], sub['p256dh'], sub['auth'])
                webpush(subscription_info={'endpoint': sub['endpoint'], 'keys': {'p256dh': sub['p256dh'], 'auth': sub['auth']}},
                        data=json.dumps(payload), vapid_private_key=os.environ['VAPID_PRIVATE_KEY_FILE'],
                        vapid_claims={'sub': os.getenv('VAPID_SUBJECT', 'https://neobricks.online')},
                        ttl=60, timeout=10, requests_session=PushSession(), headers={"Urgency": "high"})
            except WebPushException as exc:
                status = 'failed'
                code = exc.response.status_code if exc.response is not None else None
                if code in (404, 410):
                    with conn.cursor() as c:
                        c.execute('DELETE FROM push_subscriptions WHERE id=%s', (sub['id'],))
                log.warning('Push delivery failed (HTTP %s)', code)
            except Exception:
                status = 'failed'
                log.warning('Push delivery failed; check VAPID configuration.')
            with conn.cursor() as c:
                c.execute('UPDATE push_deliveries SET status=%s WHERE subscription_id=%s AND reminder_date=%s AND slot=%s',
                          (status, sub['id'], now.date(), slot))
            conn.commit()
    finally:
        conn.close()
