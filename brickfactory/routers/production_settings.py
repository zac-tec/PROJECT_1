from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from database import get_connection
from dependencies import require_admin, get_current_user
from production_entry_policy import entry_window, KEY
from services import set_text_setting, get_text_setting

router = APIRouter(tags=['production settings'])
class EntrySettings(BaseModel):
    backdate_days: int = Field(ge=0, le=3650, strict=True)

@router.get('/production-entry/settings')
def read_settings(user=Depends(get_current_user)):
    conn=get_connection()
    try:
        with conn.cursor() as c:return entry_window(c)
    finally:conn.close()

@router.put('/admin/production-entry/settings')
def update_settings(body:EntrySettings,user=Depends(require_admin)):
    conn=get_connection()
    try:
        with conn.cursor() as c:
            set_text_setting(c,KEY,str(body.backdate_days))
            result=entry_window(c)
        conn.commit()
        return result
    finally:conn.close()

@router.get('/production-entry/reminder')
def reminder(user=Depends(get_current_user)):
    now=datetime.now(ZoneInfo('Asia/Kolkata'))
    conn=get_connection()
    try:
        with conn.cursor() as c:
            start=get_text_setting(c,'daily_send_time','19:00')
            try:
                hour,minute=map(int,start.split(':'))
                valid=0<=hour<24 and 0<=minute<60
            except ValueError:valid=False
            due=valid and now.weekday()!=6 and (now.hour,now.minute)>=(hour,minute)
            c.execute('SELECT 1 FROM production_log WHERE production_date=%s',(now.date(),))
            missing=c.fetchone() is None
        return {'show': bool(due and missing), 'date':str(now.date()), 'message':
            "Please enter today's production data." if user['role']=='manager' else "The manager has not entered today's production data."}
    finally:conn.close()
