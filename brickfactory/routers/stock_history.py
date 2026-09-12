"""Read-only historical ledger and dated live finished-stock movements."""
import calendar
import datetime
from fastapi import APIRouter, Depends, HTTPException
from dependencies import require_admin
from database import get_connection
router = APIRouter(prefix='/admin/stock-history', tags=['stock history'], dependencies=[Depends(require_admin)])

@router.get('')
def history(month: str):
    try:
        first = datetime.datetime.strptime(month, '%Y-%m').date().replace(day=1)
        if first.strftime('%Y-%m') != month: raise ValueError()
        last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    except ValueError:
        raise HTTPException(422, 'Choose a month in YYYY-MM format.')
    conn = get_connection()
    try:
        with conn.cursor() as c:
            c.execute('SELECT import_key,cutover_date,confirmed_closing,notes FROM historical_ledger_imports ORDER BY cutover_date')
            imports = c.fetchall()
            c.execute('SELECT page,row_number,entry_date,data FROM historical_ledger_rows WHERE entry_date BETWEEN %s AND %s ORDER BY entry_date,page,row_number',(first,last))
            rows=c.fetchall()
            c.execute("SELECT (occurred_at AT TIME ZONE 'Asia/Kolkata')::date AS date, batch_id,quantity,reason FROM brick_batch_movements WHERE (occurred_at AT TIME ZONE 'Asia/Kolkata')::date BETWEEN %s AND %s ORDER BY occurred_at,id",(first,last))
            movements=c.fetchall()
            c.execute("SELECT COALESCE(SUM(quantity),0) AS balance FROM brick_batch_movements WHERE (occurred_at AT TIME ZONE 'Asia/Kolkata')::date < %s",(first,))
            opening=c.fetchone()['balance']
        complete=bool(imports) and first>max(x['cutover_date'] for x in imports)
        return dict(imports=imports,rows=rows,movements=movements,
                    opening=opening if complete else None,
                    closing=opening+sum(x['quantity'] for x in movements) if complete else None,
                    complete_month_ledger=complete,
                    note='Imported records are partial source history, not invoices or cost entries. September is a cutover month; use the confirmed 10 September balance. Future months show opening and closing from recorded movements, up to the latest entry.')
    finally:
        conn.close()
