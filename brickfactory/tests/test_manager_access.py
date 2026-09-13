"""Credential validation and session revocation without database mutations."""
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError
from dependencies import get_current_user, require_admin
from routers.manager_access import ManagerAccessChange
class Cursor:
 def __init__(self,row):self.row=row
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def execute(self,*args):pass
 def fetchone(self):return self.row
class Connection:
 def __init__(self,row):self.row=row
 def cursor(self):return Cursor(self.row)
 def close(self):pass
class ManagerAccessTests(unittest.TestCase):
 def session(self,version,stored):
  token=dict(username='manager',role='manager',exp=9999999999)
  if version is not None:token['session_version']=version
  with patch('dependencies.decode_access_token',return_value=token),patch('database.get_connection',return_value=Connection(stored)):
   return get_current_user(HTTPAuthorizationCredentials(scheme='Bearer',credentials='test'))
 def test_old_sessions_revoked_after_password_change(self):
  with self.assertRaises(HTTPException) as error:self.session(0,dict(user_role='manager',session_version=1))
  self.assertEqual(error.exception.status_code,401)
 def test_deleted_or_renamed_login_rejected(self):
  with self.assertRaises(HTTPException):self.session(0,None)
 def test_legacy_session_only_works_before_rotation(self):
  self.assertEqual(self.session(None,dict(user_role='manager',session_version=0))['role'],'manager')
  with self.assertRaises(HTTPException):self.session(None,dict(user_role='manager',session_version=1))
 def test_manager_cannot_administer_accounts(self):
  with self.assertRaises(HTTPException) as error:require_admin(dict(role='manager'))
  self.assertEqual(error.exception.status_code,403)
 def test_password_and_reason_validation(self):
  with self.assertRaises(ValidationError):ManagerAccessChange(current_username='manager',new_username='next_manager',new_password='short',reason='Staff change')
  with self.assertRaises(ValidationError):ManagerAccessChange(current_username='manager',new_username='next_manager',new_password='a-long-test-password',reason='     ')
if __name__=='__main__':unittest.main()
