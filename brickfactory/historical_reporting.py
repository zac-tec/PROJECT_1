"""Read-only applied history; never deduct stock again."""
from datetime import date
from services import get_rates, get_charges

def applied_days(cursor):
    cursor.execute("SELECT payload FROM historical_entry_session WHERE id=1 AND status='applied'")
    row=cursor.fetchone()
    return row['payload'] if row else {'days':[], 'recipe':{}}

def historical_cost_days(cursor, month):
    p=applied_days(cursor)
    cursor.execute("SELECT production_date FROM production_log WHERE TO_CHAR(production_date,'YYYY-MM')=%s",(month,))
    existing={str(r['production_date']) for r in cursor.fetchall()}
    charges=p.get('historical_making_charges') or get_charges(cursor)
    result=[]
    for d in p['days']:
        if d['date'][:7]!=month or d['date'] in existing or not (d['mixes'] or d['bricks']):continue
        rates=get_rates(cursor,date.fromisoformat(d['date']))
        materials={k:round(v*d['mixes'],3) for k,v in p['recipe'].items()}
        result.append(dict(production_date=d['date'],mixes_run=d['mixes'],bricks_made=d['bricks'],
            labourers_present=None,misc_expense=0,misc_note='Historical expenses not recorded',
            material_cost_total=round(sum(q*rates.get(k,0) for k,q in materials.items()),2),
            making_cost_total=round(d['bricks']*sum(float(v) for v in charges.values()),2),
            snapshot_source='historical_estimate',materials=materials))
    return result


def monthly_sales(cursor, month):
    p=applied_days(cursor)
    days=[d for d in p['days'] if d['date'][:7]==month]
    historical=sum(sum(d['sales']) for d in days)
    count=sum(len(d['sales']) for d in days)
    cursor.execute("SELECT COALESCE(SUM(bricks_purchased),0) AS bricks, COALESCE(SUM(total_amount),0) AS revenue, COALESCE(SUM(amount_paid),0) AS collected, COUNT(*) AS count FROM brick_sales WHERE TO_CHAR(sale_date,'YYYY-MM')=%s",(month,))
    r=cursor.fetchone()
    return dict(historical_bricks=historical,recorded_bricks=int(r['bricks']),total_bricks_sold=historical+int(r['bricks']),
        recorded_revenue=float(r['revenue']),recorded_collected=float(r['collected']),
        total_sales_count=count+int(r['count']),historical_sales_count=count)
