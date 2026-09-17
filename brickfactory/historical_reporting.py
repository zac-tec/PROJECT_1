"""Read-only applied history; never deduct stock again."""
from datetime import date
from services import get_rates, get_charges, get_text_setting

def applied_days(cursor):
    cursor.execute("SELECT payload FROM historical_entry_session WHERE id=1 AND status='applied'")
    row=cursor.fetchone()
    return row['payload'] if row else {'days':[], 'recipe':{}}

def historical_cost_days(cursor, month):
    p=applied_days(cursor)
    cursor.execute("SELECT production_date FROM production_log WHERE TO_CHAR(production_date,'YYYY-MM')=%s",(month,))
    existing={str(r['production_date']) for r in cursor.fetchall()}
    charges=p.get('historical_making_charges') or get_charges(cursor)
    from cost_history import labour_cost_for_hours
    cursor.execute("SELECT * FROM historical_labour_entries WHERE TO_CHAR(entry_date,'YYYY-MM')=%s",(month,))
    labour={str(r['entry_date']):r for r in cursor.fetchall()}
    source={d['date']:d for d in p['days']}
    for day in labour:source.setdefault(day,dict(date=day,mixes=0,bricks=0))
    result=[]
    for d in source.values():
        if d['date'][:7]!=month or d['date'] in existing or not (d['mixes'] or d['bricks'] or d['date'] in labour):continue
        rates=get_rates(cursor,date.fromisoformat(d['date']))
        materials={k:round(v*d['mixes'],3) for k,v in p['recipe'].items()}
        payroll=labour.get(d['date']);hours=float(payroll['labour_hours']) if payroll else None
        labour_cost=labour_cost_for_hours(hours,float(payroll['hourly_rate'])) if payroll else None
        loading=round(d['bricks']*float(charges.get('Loading',0)),2)
        union=round(d['bricks']*float(charges.get('Union',0)),2)
        result.append(dict(production_date=d['date'],mixes_run=d['mixes'],bricks_made=d['bricks'],
            labourers_present=None,misc_expense=0,misc_note='Historical expenses not recorded',
            material_cost_total=round(sum(q*rates.get(k,0) for k,q in materials.items()),2),
            making_cost_total=round(loading+union+(labour_cost or 0),2),
            loading_cost=loading,union_cost=union,labour_hours=hours,labour_cost_total=labour_cost,
            snapshot_source='historical_estimate',materials=materials))
    return result


def monthly_sales(cursor, month):
    p=applied_days(cursor)
    days=[d for d in p['days'] if d['date'][:7]==month]
    historical=sum(sum(d['sales']) for d in days)
    count=sum(len(d['sales']) for d in days)
    cursor.execute("SELECT COALESCE(SUM(bricks_purchased),0) AS bricks, COALESCE(SUM(COALESCE(taxable_amount,total_amount)),0) AS revenue, COALESCE(SUM(total_amount),0) AS billed, COALESCE(SUM(gst_amount),0) AS gst, COALESCE(SUM(amount_paid),0) AS collected, COUNT(*) AS count FROM brick_sales WHERE TO_CHAR(sale_date,'YYYY-MM')=%s",(month,))
    r=cursor.fetchone()
    saved_price=get_text_setting(cursor,'historical_sales_price_'+month,'')
    price=float(saved_price) if saved_price else None
    gst_rate=float(get_text_setting(cursor,'historical_sales_gst_'+month,'0'))
    from sales_tax import breakdown
    taxes=[breakdown(q,price,gst_rate=gst_rate) for d in days for q in d['sales']] if price is not None else []
    net_price=price/(1+gst_rate/100) if price is not None else None
    hist_net=float(sum(t['taxable_amount'] for t in taxes)) if price is not None else None
    hist_gross=float(sum(t['total_amount'] for t in taxes)) if price is not None else None
    hist_gst=float(sum(t['gst_amount'] for t in taxes)) if price is not None else None
    return dict(historical_unit_price=price, historical_base_price=net_price, historical_gst_rate=gst_rate, historical_billed=hist_gross,historical_gst=hist_gst, historical_revenue=hist_net, historical_bricks=historical,recorded_bricks=int(r['bricks']),total_bricks_sold=historical+int(r['bricks']),
        recorded_revenue=float(r['revenue']),recorded_billed=float(r['billed']),recorded_gst=float(r['gst']),recorded_collected=float(r['collected']),
        total_sales_count=count+int(r['count']),historical_sales_count=count)
