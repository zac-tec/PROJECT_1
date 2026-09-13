import json
from datetime import date
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from database import get_connection
from dependencies import require_admin
from batch_stock import factory_today
from historical_entry import calculate
router=APIRouter(prefix='/admin/historical-entry',tags=['historical entry'],dependencies=[Depends(require_admin)])
Whole=Annotated[int,Field(strict=True,ge=0,le=100000000)]
Sale=Annotated[int,Field(strict=True,gt=0,le=100000000)]
class Day(BaseModel):
    date: date
    mixes: Whole
    bricks: Whole
    damaged: Whole=0
    found_cured: Whole=0
    sales: list[Sale]=Field(default_factory=list,max_length=500)
class Draft(BaseModel):
    revision: int=Field(ge=0)
    start_date: date
    end_date: date
    opening_bricks: Whole
    recipe: dict[str,float]
    days: list[Day]=Field(default_factory=list,max_length=3000)
    recipe_note: str=Field(min_length=1,max_length=500)
    opening_confirmed_cured: bool=False

def validate(body):
    p=body.model_dump(mode='json');p.pop('revision')
    import math
    if set(p['recipe'])!={'Flyash','Sand','Cement','Chemical'} or any(not math.isfinite(v) or v<0 for v in p['recipe'].values()):raise HTTPException(422,'Enter nonnegative recipe quantities for all four materials.')
    if not p['opening_confirmed_cured']:raise HTTPException(422,'Confirm opening bricks were already eligible for sale before the start date.')
    try:r=calculate(p,factory_today())
    except ValueError as e:raise HTTPException(422,str(e))
    return p,r

@router.get('')
def get_session():
    conn=get_connection()
    try:
        with conn.cursor() as c:
            c.execute('SELECT * FROM historical_entry_session WHERE id=1');row=c.fetchone()
            c.execute('SELECT material_name,qty_per_mix FROM recipe');recipe={r['material_name']:float(r['qty_per_mix']) for r in c.fetchall()}
        return dict(session=row,recipe=recipe,today=str(factory_today()))
    finally:conn.close()

@router.post('/save')
def save(body:Draft,user=Depends(require_admin)):
    p=body.model_dump(mode='json');p.pop('revision')
    # Drafts can contain unreconciled quantities; preview/apply validates the ledger.
    conn=get_connection()
    try:
        with conn.cursor() as c:
            c.execute('SELECT pg_advisory_xact_lock(624019)')
            c.execute('SELECT revision,status FROM historical_entry_session WHERE id=1 FOR UPDATE');old=c.fetchone()
            if old and (old['status']!='draft' or old['revision']!=body.revision):raise HTTPException(409,'Session changed or is already applied. Reload before editing.')
            if not old and body.revision!=0:raise HTTPException(409,'Reload the session.')
            rev=body.revision+1
            c.execute("INSERT INTO historical_entry_session(id,revision,payload,updated_by) VALUES(1,%s,%s::jsonb,%s) ON CONFLICT(id) DO UPDATE SET revision=EXCLUDED.revision,payload=EXCLUDED.payload,updated_by=EXCLUDED.updated_by,updated_at=now()",(rev,json.dumps(p),user['username']))
        conn.commit();return dict(revision=rev)
    except Exception:conn.rollback();raise
    finally:conn.close()

@router.post('/preview')
def preview(body:Draft):return validate(body)[1]

@router.post('/apply')
def apply(body:Draft,user=Depends(require_admin)):
    p,r=validate(body)
    if not p['days']:raise HTTPException(422,'Enter at least one dated row.')
    if body.end_date>=factory_today():raise HTTPException(422,'Finish history through yesterday or earlier. Enter today through the normal daily workflow.')
    conn=get_connection()
    try:
        with conn.cursor() as c:
            c.execute('SELECT pg_advisory_xact_lock(624019)')
            c.execute('SELECT * FROM historical_entry_session WHERE id=1 FOR UPDATE');old=c.fetchone()
            if not old or old['status']!='draft' or old['revision']!=body.revision or old['payload']!=p:raise HTTPException(409,'Save this exact draft before applying. Applied sessions cannot run twice.')
            c.execute('SELECT total_bricks FROM outlet_stock WHERE id=1 FOR UPDATE');stock=c.fetchone()
            if not stock or stock['total_bricks']!=0:raise HTTPException(409,'Existing finished stock must be backed up and reset before applying history.')
            for table in ['brick_batches','brick_sales','production_log','brick_batch_movements']:
                c.execute('SELECT 1 FROM '+table+' LIMIT 1')
                if c.fetchone():raise HTTPException(409,'Existing transactions must be reset before applying history.')
            for b in r['batches']:
                source='production' if b['date'] else 'opening'
                c.execute('INSERT INTO brick_batches(source,production_date,received_date,initial_quantity,remaining_quantity) VALUES(%s,%s,%s,%s,%s) RETURNING batch_id',(source,b['date'],b['date'] or p['start_date'],b['initial'],b['remaining']))
                bid=c.fetchone()['batch_id']
                if b['remaining']:
                    c.execute("INSERT INTO brick_batch_movements(batch_id,quantity,reason,occurred_at) VALUES(%s,%s,%s,(%s::date + time '23:59:00') AT TIME ZONE 'Asia/Kolkata')",(bid,b['remaining'],'Manual historical starting position; FIFO; quantities only',p['end_date']))
            c.execute('UPDATE outlet_stock SET total_bricks=%s WHERE id=1',(r['totals']['total'],))
            c.execute('UPDATE brick_batch_state SET cutover_date=%s WHERE id=1',(p['end_date'],))
            c.execute("UPDATE historical_entry_session SET status='applied',applied_at=now(),updated_by=%s WHERE id=1",(user['username'],))
        conn.commit();return r
    except Exception:conn.rollback();raise
    finally:conn.close()
