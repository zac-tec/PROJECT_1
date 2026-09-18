"""Signed customer ledger: positive means customer owes factory; negative is credit."""
import re
from decimal import Decimal
from fastapi import HTTPException
from batch_stock import factory_today

ZERO=Decimal('0.00')
def phone_key(phone):
    key=re.sub(r'\D','',phone or '')
    if len(key)==12 and key.startswith('91'):key=key[2:]
    return key or None

def lock_account(c,customer_id):
    c.execute('SELECT * FROM customer_accounts WHERE customer_id=%s FOR UPDATE',(customer_id,))
    row=c.fetchone()
    if not row:raise HTTPException(404,'Customer account not found.')
    return row

def resolve_customer(c,name,phone,customer_id=None):
    if customer_id:
        account=lock_account(c,customer_id)
        if account.get('archived'):raise HTTPException(409,'This customer is archived. Ask the admin to restore the account first.')
        return account
    name=(name or '').strip();phone=(phone or '').strip();key=phone_key(phone)
    if not name and not phone:raise HTTPException(422,'Enter a customer name or phone number.')
    # Serialize account creation, preventing duplicate name-only records on retries.
    c.execute('SELECT pg_advisory_xact_lock(624021)')
    if key:c.execute('SELECT customer_id FROM customer_accounts WHERE phone_key=%s',(key,))
    else:c.execute('SELECT customer_id FROM customer_accounts WHERE lower(trim(name))=lower(%s)',(name,))
    rows=c.fetchall()
    if len(rows)>1:raise HTTPException(409,'Several customers have that name. Select the correct existing account.')
    if rows:return resolve_customer(c,name,phone,rows[0]['customer_id'])
    c.execute('INSERT INTO customer_accounts(name,phone,phone_key) VALUES(%s,%s,%s) RETURNING *',(name,phone,key))
    return c.fetchone()

def balance(c,customer_id):
    c.execute('SELECT COALESCE(sum(amount),0) AS balance FROM customer_ledger WHERE customer_id=%s',(customer_id,))
    return c.fetchone()['balance']

def fifo_allocations(opening,cash,totals):
    available=max(ZERO,Decimal(str(cash))-Decimal(str(opening)))
    result=[]
    for total in totals:
        applied=min(available,Decimal(str(total)));available-=applied;result.append(applied)
    return result

def allocate(c,customer_id):
    """Rebuild allocations from the immutable money ledger; opening debt is oldest."""
    lock_account(c,customer_id)
    c.execute('''SELECT COALESCE(sum(CASE WHEN l.kind='opening' OR r.kind='opening' THEN l.amount ELSE 0 END),0) AS opening,
                 COALESCE(sum(CASE WHEN l.kind NOT IN ('sale','opening') AND COALESCE(r.kind,'')!='opening' THEN -l.amount ELSE 0 END),0) AS cash
                 FROM customer_ledger l LEFT JOIN customer_ledger r ON r.entry_id=l.reverses_id WHERE l.customer_id=%s''',(customer_id,))
    sums=c.fetchone();opening=sums['opening'];cash=sums['cash']
    c.execute('SELECT sale_id,total_amount FROM brick_sales WHERE customer_id=%s ORDER BY sale_date,sale_timestamp,sale_id FOR UPDATE',(customer_id,))
    invoices=c.fetchall()
    for sale,amount in zip(invoices,fifo_allocations(opening,cash,[s['total_amount'] for s in invoices])):
        c.execute('INSERT INTO customer_allocation(customer_id,sale_id,allocated) VALUES(%s,%s,%s) ON CONFLICT(sale_id) DO UPDATE SET allocated=excluded.allocated',(customer_id,sale['sale_id'],amount))
        c.execute('UPDATE brick_sales SET amount_paid=%s WHERE sale_id=%s',(amount,sale['sale_id']))
    return balance(c,customer_id)

def record_sale(c,customer_id,sale_id,total,received,user,day,replace=False):
    if replace:
        c.execute("SELECT 1 FROM customer_ledger WHERE customer_id=%s AND kind IN ('payment','refund','reversal') LIMIT 1",(customer_id,))
        if c.fetchone():raise HTTPException(409,'This customer has admin payment activity. Contact admin before correcting this sale.')
    for kind,amount in [('sale',total),('sale_payment',-Decimal(str(received)))]:
        c.execute("SELECT entry_id FROM customer_ledger WHERE sale_id=%s AND kind=ANY(%s)",(sale_id,['sale'] if kind=='sale' else ['sale_payment','import_payment']))
        row=c.fetchone()
        if row:
            c.execute('UPDATE customer_ledger SET amount=%s,note=%s WHERE entry_id=%s',(amount,'Dated sale correction; previous invoice retained in audit',row['entry_id']))
        else:
            c.execute('INSERT INTO customer_ledger(customer_id,kind,amount,sale_id,effective_date,recorded_by) VALUES(%s,%s,%s,%s,%s,%s)',(customer_id,kind,amount,sale_id,day,user))
    return allocate(c,customer_id)

def migrate_accounts(c):
    c.execute('SELECT pg_advisory_xact_lock(624022)')
    c.execute('SELECT * FROM brick_sales WHERE customer_id IS NULL ORDER BY sale_date,sale_timestamp,sale_id FOR UPDATE')
    rows=c.fetchall();ids=set()
    for sale in rows:
        account=resolve_customer(c,sale['customer_name'],sale['customer_mobile'])
        cid=account['customer_id'];ids.add(cid)
        c.execute('UPDATE brick_sales SET customer_id=%s,amount_received=amount_paid WHERE sale_id=%s',(cid,sale['sale_id']))
        for kind,amount in [('sale',sale['total_amount']),('import_payment',-sale['amount_paid'])]:
            c.execute('INSERT INTO customer_ledger(customer_id,kind,amount,sale_id,effective_date,recorded_by,note) VALUES(%s,%s,%s,%s,%s,%s,%s)',(cid,kind,amount,sale['sale_id'],sale['sale_date'],'migration','Imported existing invoice/payment totals; original payment date may be unknown'))
    for cid in ids:allocate(c,cid)

def cash_received(c,start,end):
    c.execute('''SELECT COALESCE(sum(-l.amount),0) AS amount FROM customer_ledger l
                 LEFT JOIN customer_ledger r ON r.entry_id=l.reverses_id
                 WHERE l.effective_date>=%s AND l.effective_date<=%s
                 AND l.kind IN ('sale_payment','import_payment','payment','refund','reversal')
                 AND COALESCE(r.kind,'')!='opening' ''',(start,end))
    return c.fetchone()['amount']
