"""Dated finished-brick stock. All writers lock the outlet row first."""
import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from fastapi import HTTPException


def factory_today():
    return datetime.datetime.now(ZoneInfo('Asia/Kolkata')).date()


def initialize_batches():
    from database import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(Path(__file__).with_name('migration_brick_batches.sql').read_text())
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def lock_stock(cursor):
    cursor.execute('SELECT total_bricks FROM outlet_stock WHERE id=1 FOR UPDATE')
    if cursor.fetchone() is None:
        raise HTTPException(409, 'Outlet stock has not been initialized.')


def stage(production_date, source, today):
    if source != 'production':
        return 'fully_cured'
    age = (today - production_date).days
    return 'fully_cured' if age >= 14 else 'early_sale' if age >= 7 else 'curing'


def stock_summary(cursor, today=None):
    today = today or factory_today()
    cursor.execute('SELECT * FROM brick_batches WHERE remaining_quantity > 0 ORDER BY COALESCE(production_date, received_date), batch_id')
    result = dict(total_bricks=0, curing=0, early_sale=0, fully_cured=0, saleable=0, as_of=str(today), batches=[])
    for row in cursor.fetchall():
        category = stage(row['production_date'], row['source'], today)
        qty = row['remaining_quantity']
        result[category] += qty
        result['total_bricks'] += qty
        result['batches'].append(dict(batch_id=row['batch_id'], source=row['source'],
            production_date=str(row['production_date']) if row['production_date'] else None,
            received_date=str(row['received_date']), received_at=row['received_at'].isoformat(),
            age_days=(today-row['production_date']).days if row['production_date'] else None,
            early_sale_date=str(row['production_date']+datetime.timedelta(days=7)) if row['production_date'] else None,
            fully_cured_date=str(row['production_date']+datetime.timedelta(days=14)) if row['production_date'] else None,
            initial_quantity=row['initial_quantity'], remaining_quantity=qty, stage=category))
    result['saleable'] = result['early_sale'] + result['fully_cured']
    return result


def sync_total(cursor):
    cursor.execute('UPDATE outlet_stock SET total_bricks=(SELECT COALESCE(SUM(remaining_quantity),0) FROM brick_batches) WHERE id=1 RETURNING total_bricks')
    return cursor.fetchone()['total_bricks']


def movement(cursor, batch_id, quantity, reason, sale_id=None):
    cursor.execute('INSERT INTO brick_batch_movements(batch_id, quantity, reason, sale_id) VALUES(%s,%s,%s,%s)',
                   (batch_id, quantity, reason, sale_id))


def production_change(cursor, date, delta):
    if not delta:
        return
    cursor.execute('SELECT cutover_date FROM brick_batch_state WHERE id=1')
    cutover = cursor.fetchone()['cutover_date']
    if date <= cutover:
        cursor.execute("SELECT * FROM brick_batches WHERE source='opening' FOR UPDATE")
    else:
        cursor.execute("SELECT * FROM brick_batches WHERE source='production' AND production_date=%s FOR UPDATE", (date,))
    row = cursor.fetchone()
    if row is None:
        if delta < 0:
            raise HTTPException(409, 'Cannot reduce a production batch that does not exist.')
        cursor.execute("INSERT INTO brick_batches(source,production_date,received_date,initial_quantity,remaining_quantity) VALUES('production',%s,%s,%s,%s) RETURNING batch_id", (date,date,delta,delta))
        batch_id = cursor.fetchone()['batch_id']
    else:
        if row['remaining_quantity'] + delta < 0:
            raise HTTPException(409, 'This correction would remove bricks already sold or adjusted. Correct those records first.')
        batch_id = row['batch_id']
        cursor.execute('UPDATE brick_batches SET initial_quantity=initial_quantity+%s, remaining_quantity=remaining_quantity+%s WHERE batch_id=%s', (delta,delta,batch_id))
    movement(cursor,batch_id,delta,'production correction or entry')
    sync_total(cursor)


def allocate_sale(cursor, sale_id, quantity, today=None):
    today = today or factory_today()
    summary = stock_summary(cursor,today)
    if quantity > summary['saleable']:
        raise HTTPException(409, f"Only {summary['saleable']} bricks are saleable; {summary['curing']} are still under 7 days old. Requested: {quantity}.")
    # Consume the oldest eligible stock first. Receipt date is the age reference
    # for opening stock, returns, and transfers because they arrive fully cured.
    cursor.execute("SELECT * FROM brick_batches WHERE remaining_quantity>0 AND (source<>'production' OR production_date<=%s) ORDER BY COALESCE(production_date,received_date),batch_id FOR UPDATE", (today-datetime.timedelta(days=7),))
    remaining = quantity
    for row in cursor.fetchall():
        take = min(remaining,row['remaining_quantity'])
        if not take:
            break
        cursor.execute('UPDATE brick_batches SET remaining_quantity=remaining_quantity-%s WHERE batch_id=%s',(take,row['batch_id']))
        cursor.execute('INSERT INTO brick_sale_allocations(sale_id,batch_id,quantity) VALUES(%s,%s,%s)',(sale_id,row['batch_id'],take))
        movement(cursor,row['batch_id'],-take,'sale',sale_id)
        remaining -= take
    if remaining:
        raise HTTPException(409, 'Stock changed. Reload and try again.')
    sync_total(cursor)


def restore_sale(cursor, sale_id):
    cursor.execute('SELECT batch_id,quantity FROM brick_sale_allocations WHERE sale_id=%s',(sale_id,))
    rows = cursor.fetchall()
    if not rows:
        raise HTTPException(409, 'This historical sale has no batch allocation and cannot be edited.')
    for row in rows:
        cursor.execute('UPDATE brick_batches SET remaining_quantity=remaining_quantity+%s WHERE batch_id=%s',(row['quantity'],row['batch_id']))
        movement(cursor,row['batch_id'],row['quantity'],'sale correction reversal',sale_id)
    cursor.execute('DELETE FROM brick_sale_allocations WHERE sale_id=%s',(sale_id,))
    sync_total(cursor)


def adjust_batches(cursor, quantity, kind, batch_id, note):
    if quantity > 0:
        if kind not in ('return','transfer'):
            raise HTTPException(422, 'Choose Return or Transfer in for added stock.')
        cursor.execute('INSERT INTO brick_batches(source,received_date,initial_quantity,remaining_quantity) VALUES(%s,%s,%s,%s) RETURNING batch_id',(kind,factory_today(),quantity,quantity))
        batch_id = cursor.fetchone()['batch_id']
    else:
        if kind not in ('damage','transfer_out') or not batch_id:
            raise HTTPException(422, 'Choose Damage/loss or Transfer out and select the affected batch.')
        cursor.execute('SELECT remaining_quantity FROM brick_batches WHERE batch_id=%s FOR UPDATE',(batch_id,))
        row = cursor.fetchone()
        if not row or row['remaining_quantity'] + quantity < 0:
            raise HTTPException(409, 'The selected batch does not have enough bricks for this adjustment.')
        cursor.execute('UPDATE brick_batches SET remaining_quantity=remaining_quantity+%s WHERE batch_id=%s',(quantity,batch_id))
    movement(cursor,batch_id,quantity,kind+': '+note)
    return sync_total(cursor), batch_id
