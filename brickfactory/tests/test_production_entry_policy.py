import unittest
from unittest.mock import patch, MagicMock
from datetime import date
from fastapi import HTTPException
from production_entry_policy import validate_entry_date,entry_window

class WindowTests(unittest.TestCase):
 def setUp(self):
  self.c=MagicMock();self.c.fetchone.return_value={'cutover_date':date(2026,9,12)}
  self.today=patch('production_entry_policy.factory_today',return_value=date(2026,9,16));self.today.start();self.addCleanup(self.today.stop)
 def test_default_today_and_yesterday(self):
  with patch('production_entry_policy.get_text_setting',return_value='1'):
   for day in (15,16):self.assertEqual(validate_entry_date(self.c,date(2026,9,day)),date(2026,9,day))
   for day in (14,17):
    with self.assertRaises(HTTPException):validate_entry_date(self.c,date(2026,9,day))
 def test_admin_expansion_and_finalized_history(self):
  with patch('production_entry_policy.get_text_setting',return_value='10'):
   self.assertEqual(entry_window(self.c)['earliest_date'],date(2026,9,13))
   self.assertEqual(validate_entry_date(self.c,date(2026,9,13)),date(2026,9,13))
   with self.assertRaises(HTTPException):validate_entry_date(self.c,date(2026,9,12))
 def test_zero_days(self):
  with patch('production_entry_policy.get_text_setting',return_value='0'):
   self.assertEqual(validate_entry_date(self.c),date(2026,9,16))
   with self.assertRaises(HTTPException):validate_entry_date(self.c,date(2026,9,15))
if __name__=='__main__':unittest.main()
