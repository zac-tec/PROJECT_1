import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock
from push_notifications import IST, reminder_roles, validate_subscription, run_production_reminders
import base64

class PushTests(unittest.TestCase):
    def test_schedule(self):
        for hour in range(24):
            now=datetime(2026,9,16,hour,0,tzinfo=IST)
            self.assertEqual(reminder_roles(now,20), ('manager',) if hour==20 else ())
            self.assertEqual(reminder_roles(now,22), ('manager','admin') if hour==22 else ())
        self.assertEqual(reminder_roles(datetime(2026,9,20,22,0,tzinfo=IST),22),())
        self.assertEqual(reminder_roles(datetime(2026,9,16,22,1,tzinfo=IST),22),())
    def test_endpoints(self):
        p=base64.urlsafe_b64encode(b'\x04'+b'a'*64).decode().rstrip('=')
        a=base64.urlsafe_b64encode(b'b'*16).decode().rstrip('=')
        validate_subscription('https://fcm.googleapis.com/fcm/send/example',p,a)
        for endpoint in ('https://127.0.0.1/push','http://fcm.googleapis.com/test','https://fcm.googleapis.com.evil.test/x','https://user@fcm.googleapis.com/x'):
            with self.assertRaises(ValueError):validate_subscription(endpoint,p,a)
    def test_existing_production_prevents_delivery(self):
        conn=MagicMock();c=conn.cursor.return_value.__enter__.return_value
        c.fetchall.return_value=[{'id':1}];c.fetchone.return_value={'exists':1}
        with patch('push_notifications.datetime') as clock, patch('push_notifications.get_connection',return_value=conn),patch('push_notifications.public_config',return_value={'enabled':True}),patch('pywebpush.webpush') as send:
            clock.now.return_value=datetime(2026,9,16,22,0,tzinfo=IST)
            run_production_reminders(22)
            send.assert_not_called()
            self.assertFalse(any('INSERT INTO push_deliveries' in str(x) for x in c.execute.call_args_list))
    def test_duplicate_claim_prevents_delivery(self):
        conn=MagicMock();c=conn.cursor.return_value.__enter__.return_value
        c.fetchall.return_value=[{'id':1,'username':'test','session_version':0}]
        c.fetchone.side_effect=[None,{'exists':1},None]
        with patch('push_notifications.datetime') as clock, patch('push_notifications.get_connection',return_value=conn),patch('push_notifications.public_config',return_value={'enabled':True}),patch('pywebpush.webpush') as send:
            clock.now.return_value=datetime(2026,9,16,22,0,tzinfo=IST)
            run_production_reminders(22);send.assert_not_called()

if __name__=='__main__':unittest.main()
