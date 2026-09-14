"""Admin-only payroll backfill, independent of stock and production writes."""
from datetime import date,timedelta
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from database import get_connection
from dependencies import require_admin
from historical_reporting import applied_days
from batch_stock import factory_today
router=APIRouter(prefix='/admin/historical-labour',dependencies=[Depends(require_admin)])
def bounds(c):
    p=applied_days(c)
    if not p['days']:raise HTTPException(409,'No applied history exists.')
    end=date.fromisoformat(p['end_date'])
    start=max(date.fromisoformat(p['start_date']),end.replace(day=1))
    c.execute('SELECT MIN(production_date) AS first FROM production_log');first=c.fetchone()['first']
    last=min(factory_today()-timedelta(days=1),first-timedelta(days=1) if first else end)
    return p,start,last
@router.get('')
def get_entries():
    conn=get_connection()
    try:
        with conn.cursor() as c:
            p,start,last=bounds(c)
            c.execute('SELECT * FROM historical_labour_entries WHERE entry_date BETWEEN %s AND %s',(start,last))
            saved={str(r['entry_date']):r for r in c.fetchall()}
            production={d['date']:d['bricks'] for d in p['days']}
            rows=[];day=start
            while day<=last:
                r=saved.get(str(day));rows.append(dict(date=str(day),bricks=production.get(str(day),0),hours=float(r['labour_hours']) if r else None,revision=r['revision'] if r else 0));day+=timedelta(days=1)
        return dict(days=rows,hourly_rate=81.25)
    finally:conn.close()
class Entry(BaseModel):
    date:date
    hours:float=Field(ge=0,le=10000,allow_inf_nan=False,multiple_of=0.01)
    revision:int=Field(ge=0)
class Entries(BaseModel):
    days:list[Entry]=Field(min_length=1,max_length=100)
@router.post('')
def save_entries(body:Entries,user=Depends(require_admin)):
    conn=get_connection()
    try:
        with conn.cursor() as c:
            c.execute('SELECT pg_advisory_xact_lock(624021)')
            _,start,last=bounds(c)
            if len({d.date for d in body.days})!=len(body.days):raise HTTPException(422,'Duplicate dates.')
            for d in body.days:
                if not start<=d.date<=last:raise HTTPException(422,'Date is outside the historical labour period.')
                c.execute('SELECT labour_hours,revision FROM historical_labour_entries WHERE entry_date=%s FOR UPDATE',(d.date,));old=c.fetchone()
                if d.revision!=(old['revision'] if old else 0):raise HTTPException(409,'Hours changed in another session. Reload before saving.')
                c.execute('INSERT INTO historical_labour_entries(entry_date,labour_hours,updated_by) VALUES(%s,%s,%s) ON CONFLICT(entry_date) DO UPDATE SET labour_hours=EXCLUDED.labour_hours,revision=historical_labour_entries.revision+1,updated_by=EXCLUDED.updated_by,updated_at=now()',(d.date,d.hours,user['username']))
                c.execute('INSERT INTO historical_labour_audit(entry_date,old_hours,new_hours,changed_by) VALUES(%s,%s,%s,%s)',(d.date,old['labour_hours'] if old else None,d.hours,user['username']))
        conn.commit();return dict(saved=len(body.days))
    except Exception:conn.rollback();raise
    finally:conn.close()
