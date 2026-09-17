from decimal import Decimal
import json
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,model_validator
from typing import Literal
from database import get_connection
from dependencies import get_current_user,require_admin
from batch_stock import factory_today
from customer_accounts import resolve_customer,lock_account,balance,allocate,phone_key
from psycopg2 import errors
router=APIRouter(prefix='/customer-accounts',tags=['customer accounts'])

class CustomerCreate(BaseModel):
    name:str=Field(default='',max_length=100)
    phone:str=Field(default='',max_length=30)
    @model_validator(mode='after')
    def identity(self):
        if not self.name.strip() and not self.phone.strip():raise ValueError('Enter a name or phone number.')
        return self

class MoneyEntry(BaseModel):
    kind:Literal['payment','refund','opening']
    amount:Decimal=Field(max_digits=12,decimal_places=2)
    note:str=Field(min_length=3,max_length=500)
    request_id:UUID

class Reversal(BaseModel):
    note:str=Field(min_length=3,max_length=500)
    request_id:UUID

def detail(c,cid):
    c.execute('SELECT * FROM customer_accounts WHERE customer_id=%s',(cid,));account=c.fetchone()
    if not account:raise HTTPException(404,'Customer not found.')
    c.execute('''SELECT l.*, EXISTS(SELECT 1 FROM customer_ledger x WHERE x.reverses_id=l.entry_id) AS reversed,
                 sum(l.amount) OVER(ORDER BY l.entry_id) AS running_balance FROM customer_ledger l
                 WHERE customer_id=%s ORDER BY entry_id''',(cid,))
    entries=c.fetchall()
    c.execute('''SELECT sale_id,sale_date,bricks_purchased,total_amount,amount_paid,amount_received,
                 total_amount-amount_paid AS outstanding FROM brick_sales WHERE customer_id=%s
                 ORDER BY sale_date,sale_timestamp,sale_id''',(cid,))
    invoices=c.fetchall()
    return dict(customer=account,balance=balance(c,cid),entries=entries,invoices=invoices)

@router.get('')
def customers(q:str='',include_archived:bool=False,user=Depends(get_current_user)):
    conn=get_connection()
    try:
        with conn.cursor() as c:
            c.execute('''SELECT a.customer_id,a.name,a.phone,a.archived,COALESCE(sum(l.amount),0) AS balance
              FROM customer_accounts a LEFT JOIN customer_ledger l USING(customer_id)
              WHERE (a.name ILIKE %s OR a.phone ILIKE %s) AND (NOT a.archived OR %s) GROUP BY a.customer_id ORDER BY lower(a.name),a.customer_id''',('%'+q+'%','%'+q+'%',include_archived and user['role']=='admin'))
            return {'customers':c.fetchall()}
    finally:conn.close()

@router.post('')
def create_customer(body:CustomerCreate,user=Depends(require_admin)):
    conn=get_connection()
    try:
        with conn.cursor() as c:account=resolve_customer(c,body.name,body.phone)
        conn.commit();return account
    except Exception:conn.rollback();raise
    finally:conn.close()

@router.get('/{cid}')
def account_detail(cid:int,user=Depends(require_admin)):
    conn=get_connection()
    try:
        with conn.cursor() as c:return detail(c,cid)
    finally:conn.close()

@router.post('/{cid}/entries')
def add_entry(cid:int,body:MoneyEntry,user=Depends(require_admin)):
    conn=get_connection()
    try:
        with conn.cursor() as c:
            account=lock_account(c,cid)
            if account['archived']:raise HTTPException(409,'Restore this archived account before changing its transactions.')
            c.execute('SELECT customer_id,request_data FROM customer_ledger WHERE request_id=%s',(str(body.request_id),))
            old=c.fetchone()
            if old:
                if old['request_data']!=body.model_dump(mode='json'):raise HTTPException(409,'This submission already exists with different values. Reopen the account before entering another transaction.')
                if old['customer_id']!=cid:raise HTTPException(409,'Request belongs to another customer.')
                return detail(c,cid)
            current=balance(c,cid)
            if body.kind=='opening':
                amount=body.amount-current
                note=f'Complete balance set to {body.amount}; previously {current}. '+body.note
            else:
                if body.amount<=0:raise HTTPException(422,'Enter a positive amount.')
                if body.kind=='refund' and body.amount>max(Decimal(0),-current):
                    raise HTTPException(409,'Refund cannot exceed the customer credit.')
                amount=-body.amount if body.kind=='payment' else body.amount
                note=body.note
            c.execute('INSERT INTO customer_ledger(customer_id,kind,amount,effective_date,recorded_by,note,request_id) VALUES(%s,%s,%s,%s,%s,%s,%s)',(cid,body.kind,amount,factory_today(),user['username'],note,str(body.request_id)))
            c.execute('UPDATE customer_ledger SET request_data=%s::jsonb WHERE request_id=%s',(body.model_dump_json(),str(body.request_id)))
            allocate(c,cid);result=detail(c,cid)
        conn.commit();return result
    except Exception:conn.rollback();raise
    finally:conn.close()

@router.post('/{cid}/entries/{entry_id}/reverse')
def reverse_entry(cid:int,entry_id:int,body:Reversal,user=Depends(require_admin)):
    conn=get_connection()
    try:
        with conn.cursor() as c:
            account=lock_account(c,cid)
            if account['archived']:raise HTTPException(409,'Restore this archived account before changing its transactions.')
            c.execute('SELECT * FROM customer_ledger WHERE entry_id=%s AND customer_id=%s',(entry_id,cid));row=c.fetchone()
            if not row or row['kind'] in ('sale','reversal'):raise HTTPException(422,'This entry cannot be reversed here.')
            c.execute('SELECT 1 FROM customer_ledger WHERE reverses_id=%s',(entry_id,))
            if c.fetchone():return detail(c,cid)
            c.execute("INSERT INTO customer_ledger(customer_id,kind,amount,reverses_id,effective_date,recorded_by,note,request_id) VALUES(%s,'reversal',%s,%s,%s,%s,%s,%s)",(cid,-row['amount'],entry_id,factory_today(),user['username'],body.note,str(body.request_id)))
            c.execute('UPDATE customer_ledger SET request_data=%s::jsonb WHERE request_id=%s',(body.model_dump_json(),str(body.request_id)))
            allocate(c,cid);result=detail(c,cid)
        conn.commit();return result
    except Exception:conn.rollback();raise
    finally:conn.close()


class Profile(CustomerCreate):
    address:str=Field(default='',max_length=1000)
    notes:str=Field(default='',max_length=2000)

class AccountAction(BaseModel):
    action:Literal['archive','restore','delete']

@router.put('/{cid}/profile')
def update_profile(cid:int,body:Profile,user=Depends(require_admin)):
    conn=get_connection()
    try:
        with conn.cursor() as c:
            c.execute('SELECT pg_advisory_xact_lock(624021)')
            lock_account(c,cid)
            c.execute("INSERT INTO customer_account_audit(customer_id,action,recorded_by,previous_record) SELECT customer_id,'edit profile',%s,to_jsonb(a) FROM customer_accounts a WHERE customer_id=%s",(user['username'],cid))
            c.execute('UPDATE customer_accounts SET name=%s,phone=%s,phone_key=%s,address=%s,notes=%s WHERE customer_id=%s',
                      (body.name.strip(),body.phone.strip(),phone_key(body.phone),body.address.strip(),body.notes.strip(),cid))
            result=detail(c,cid)
        conn.commit();return result
    except errors.UniqueViolation:
        conn.rollback();raise HTTPException(409,'That phone number belongs to another customer account. Select that customer instead.')
    except Exception:conn.rollback();raise
    finally:conn.close()

@router.post('/{cid}/manage')
def manage_account(cid:int,body:AccountAction,user=Depends(require_admin)):
    conn=get_connection()
    try:
        with conn.cursor() as c:
            lock_account(c,cid)
            if body.action=='delete':
                c.execute('SELECT EXISTS(SELECT 1 FROM customer_ledger WHERE customer_id=%s) OR EXISTS(SELECT 1 FROM brick_sales WHERE customer_id=%s) AS used',(cid,cid))
                if c.fetchone()['used']:raise HTTPException(409,'This account has history. Remove incorrect money entries first, then archive the settled account.')
            if body.action=='archive' and balance(c,cid)!=0:
                raise HTTPException(409,'Settle this account or remove an incorrect entry before archiving. Outstanding debt or credit cannot be hidden.')
            c.execute('INSERT INTO customer_account_audit(customer_id,action,recorded_by,previous_record) SELECT customer_id,%s,%s,to_jsonb(a) FROM customer_accounts a WHERE customer_id=%s',(body.action,user['username'],cid))
            if body.action=='delete':c.execute('DELETE FROM customer_accounts WHERE customer_id=%s',(cid,))
            else:c.execute('UPDATE customer_accounts SET archived=%s WHERE customer_id=%s',(body.action=='archive',cid))
        conn.commit();return {'action':body.action,'customer_id':cid}
    except Exception:conn.rollback();raise
    finally:conn.close()
