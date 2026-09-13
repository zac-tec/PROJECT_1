"""Admin-only manager credential rotation with immediate token revocation."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, SecretStr, field_validator
from psycopg2 import errors
from database import get_connection
from dependencies import require_admin
from auth_utils import hash_password

router=APIRouter(prefix='/admin/manager-access',tags=['manager access'],dependencies=[Depends(require_admin)])
class ManagerAccessChange(BaseModel):
    current_username: str = Field(min_length=1,max_length=50)
    new_username: str = Field(min_length=3,max_length=50,pattern=r'^[A-Za-z0-9_.-]+$')
    new_password: SecretStr
    reason: str = Field(min_length=5,max_length=500)

    @field_validator('new_password')
    @classmethod
    def password_length(cls,v):
        raw=v.get_secret_value()
        if len(raw)<12 or len(raw.encode('utf-8'))>72:
            raise ValueError('Use at least 12 characters and at most 72 UTF-8 bytes.')
        return v

    @field_validator('reason')
    @classmethod
    def reason_required(cls,v):
        if len(v.strip())<5:raise ValueError('Enter the reason for this change.')
        return v.strip()

@router.get('')
def list_managers():
    conn=get_connection()
    try:
        with conn.cursor() as c:
            c.execute("SELECT username FROM system_users WHERE user_role='manager' ORDER BY username")
            managers=c.fetchall()
            c.execute('SELECT changed_at,changed_by,previous_username,new_username,reason FROM manager_access_audit ORDER BY id DESC LIMIT 20')
            audit=c.fetchall()
        return dict(managers=managers,audit=audit)
    finally:conn.close()

@router.post('')
def change_manager(body:ManagerAccessChange,user=Depends(require_admin)):
    hashed=hash_password(body.new_password.get_secret_value())
    conn=get_connection()
    try:
        with conn.cursor() as c:
            c.execute("SELECT username FROM system_users WHERE username=%s AND user_role='manager' FOR UPDATE",(body.current_username,))
            if not c.fetchone():raise HTTPException(404,'Manager account not found. Refresh the list.')
            c.execute("UPDATE system_users SET username=%s,password_hash=%s,session_version=session_version+1 WHERE username=%s AND user_role='manager'",(body.new_username,hashed,body.current_username))
            c.execute('INSERT INTO manager_access_audit(changed_by,previous_username,new_username,reason) VALUES(%s,%s,%s,%s)',(user['username'],body.current_username,body.new_username,body.reason))
        conn.commit()
    except errors.UniqueViolation:
        conn.rollback();raise HTTPException(409,'That username is already in use.')
    except Exception:
        conn.rollback();raise
    finally:conn.close()
    from routers.presence import _users,_lock
    with _lock:_users.pop(body.current_username,None)
    return dict(username=body.new_username,message='Manager login updated. All previous sessions are revoked.')
