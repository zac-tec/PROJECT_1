"""
DASHBOARD / ANALYTICS ROUTES
Read-only endpoints that power the admin Dashboard page: trend charts,
cost breakdown, sales analytics, and a few "interesting facts" pulled
from real data. Nothing here writes to the database.

To add a new dashboard widget later: add a new @router.get function here,
and a matching chart/card in frontend/js/dashboard.js.
"""

import datetime
from cost_history import labour_cost_for_hours
from fastapi import APIRouter, HTTPException, Depends
from dependencies import require_admin
from database import get_connection
from services import get_recipe, get_rates, get_charges, get_bricks_per_mix, get_monthly_overhead

router = APIRouter(prefix="/admin/dashboard", tags=["dashboard"], dependencies=[Depends(require_admin)])


# ---------------------------------------------------------
# Today's Activity — powers the "Today's Activity" card and the
# notification badge on the Dashboard sidebar button.
# ---------------------------------------------------------
@router.get("/today-activity")
def today_activity():
    from batch_stock import factory_today
    return activity_for_date(factory_today())

@router.get('/activity')
def dated_activity(date: datetime.date):
    from batch_stock import factory_today
    if date>factory_today():raise HTTPException(422,'Choose today or an earlier date.')
    return activity_for_date(date)

def activity_for_date(target_date):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        today = target_date

        cursor.execute(
            """SELECT timestamp_entered, mixes_run, bricks_made, labourers_present, labour_hours, misc_expense, misc_note, is_corrected
               FROM production_log WHERE production_date = %s""",
            (today,),
        )
        prod_row = cursor.fetchone()
        production = None
        if prod_row is not None:
            production = {
                "timestamp": str(prod_row["timestamp_entered"]),
                "mixes": prod_row["mixes_run"],
                "bricks_produced": prod_row["bricks_made"],
                "labourers": prod_row["labourers_present"],
                "labour_hours": float(prod_row["labour_hours"]) if prod_row["labour_hours"] is not None else None,
                "labour_cost": labour_cost_for_hours(prod_row["labour_hours"]) if prod_row["labour_hours"] is not None else None,
                "misc_amount": float(prod_row["misc_expense"]),
                "misc_note": prod_row["misc_note"],
                "is_corrected": prod_row["is_corrected"],
            }

        cursor.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(bricks_purchased), 0) AS total_bricks,
                      COALESCE(SUM(total_amount), 0) AS total_revenue, COALESCE(SUM(amount_paid), 0) AS total_paid
               FROM brick_sales WHERE sale_date = %s""",
            (today,),
        )
        sales_row = cursor.fetchone()
        sales = {
            "count": sales_row["count"],
            "total_bricks": sales_row["total_bricks"],
            "total_revenue": round(float(sales_row["total_revenue"]), 2),
            "total_paid": round(float(sales_row["total_paid"]), 2),
        }

        from customer_accounts import cash_received
        sales["total_paid"]=float(cash_received(cursor,today,today))
        from historical_reporting import applied_days
        from production_metrics import daily_averages
        history=next((d for d in applied_days(cursor)['days'] if d['date']==str(today)),None)
        cursor.execute('SELECT labour_hours FROM historical_labour_entries WHERE entry_date=%s',(today,))
        hours_row=cursor.fetchone()
        if production is None and (history or hours_row):
            history=history or dict(mixes=0,bricks=0,sales=[])
            hours=float(hours_row['labour_hours']) if hours_row else None
            production=dict(timestamp=None,mixes=history['mixes'],bricks_produced=history['bricks'],labourers=None,labour_hours=hours,
                labour_cost=labour_cost_for_hours(hours) if hours is not None else None,misc_amount=None,misc_note='Not recorded',is_corrected='no')
        if production:production.update(daily_averages(production['bricks_produced'],production['mixes'],production['labour_hours']))
        cursor.execute('SELECT sale_id,sale_timestamp,customer_name,customer_mobile,bricks_purchased,cost_per_brick,total_amount,amount_paid FROM brick_sales WHERE sale_date=%s ORDER BY sale_timestamp,sale_id',(today,))
        sale_entries=[dict(sale_id=r['sale_id'],time=str(r['sale_timestamp']),customer=r['customer_name'],phone=r['customer_mobile'],bricks=r['bricks_purchased'],price=float(r['cost_per_brick']),amount=float(r['total_amount']),paid=float(r['amount_paid'])) for r in cursor.fetchall()]
        if history:
            for q in history['sales']:sale_entries.append(dict(sale_id=None,time=None,customer=None,phone=None,bricks=q,price=None,amount=None,paid=None))
            if history['sales']:
                sales['count']+=len(history['sales']);sales['total_bricks']+=sum(history['sales'])
                sales['total_revenue']=None;sales['total_paid']=None

        cursor.execute(
            """SELECT adjustment_timestamp, change_amount, note, resulting_stock
               FROM outlet_stock_adjustments WHERE adjustment_date = %s ORDER BY adjustment_timestamp""",
            (today,),
        )
        stock_adjustments = [
            {"time": r["adjustment_timestamp"].strftime("%H:%M:%S"), "change_amount": r["change_amount"], "note": r["note"], "resulting_stock": r["resulting_stock"]}
            for r in cursor.fetchall()
        ]

        cursor.execute(
            """SELECT change_timestamp, material_name, old_rate, new_rate
               FROM rate_history WHERE change_date = %s ORDER BY change_timestamp""",
            (today,),
        )
        rate_changes = [
            {"time": r["change_timestamp"].strftime("%H:%M:%S"), "material": r["material_name"],
             "old_rate": float(r["old_rate"]), "new_rate": float(r["new_rate"])}
            for r in cursor.fetchall()
        ]

        cursor.execute(
            """SELECT change_timestamp, charge_name, old_value, new_value
               FROM making_charges_history WHERE change_date = %s ORDER BY change_timestamp""",
            (today,),
        )
        charge_changes = [
            {"time": r["change_timestamp"].strftime("%H:%M:%S"), "charge_name": r["charge_name"],
             "old_value": float(r["old_value"]), "new_value": float(r["new_value"])}
            for r in cursor.fetchall()
        ]

        cursor.execute(
            "SELECT id, occurred_at AT TIME ZONE 'Asia/Kolkata' AS local_time, actor, event_type, details FROM factory_activity_events WHERE occurred_at >= (%s::date::timestamp AT TIME ZONE 'Asia/Kolkata') AND occurred_at < ((%s::date + 1)::timestamp AT TIME ZONE 'Asia/Kolkata') ORDER BY id DESC",
            (today, today),
        )
        operational_events = [{"id": row["id"], "time": str(row["local_time"].time()),
                               "actor": row["actor"], "type": row["event_type"], "details": row["details"]}
                              for row in cursor.fetchall()]
        cursor.execute("SELECT billing_month, bill_type, amount, entry_timestamp FROM utility_bills WHERE entry_date = %s ORDER BY entry_timestamp DESC", (today,))
        updated_bills = [{"month": row["billing_month"], "bill_type": row["bill_type"],
                         "amount": float(row["amount"]), "time": str(row["entry_timestamp"])}
                        for row in cursor.fetchall()]

        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    activity_count = (
        len(operational_events) + (1 if production else 0) + sales["count"] + len(stock_adjustments) + len(rate_changes) + len(charge_changes)
    )

    return {
        "date": today.strftime("%Y-%m-%d"),
        "operational_events": operational_events,
        "updated_bills": updated_bills,
        "sale_entries": sale_entries,
        "production": production,
        "sales": sales,
        "stock_adjustments": stock_adjustments,
        "rate_changes": rate_changes,
        "charge_changes": charge_changes,
        "activity_count": activity_count,
    }


# ---------------------------------------------------------
# Production Trends
# ---------------------------------------------------------
@router.get("/daily-production")
def daily_production(days: int = 30):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cutoff = datetime.date.today() - datetime.timedelta(days=days - 1)
        cursor.execute(
            """SELECT production_date, mixes_run, bricks_made FROM production_log
               WHERE production_date >= %s ORDER BY production_date""",
            (cutoff,),
        )
        rows = cursor.fetchall()
        from historical_reporting import applied_days
        existing={str(r['production_date']) for r in rows}
        rows += [dict(production_date=datetime.date.fromisoformat(d['date']),mixes_run=d['mixes'],bricks_made=d['bricks']) for d in applied_days(cursor)['days'] if d['date'] >= str(cutoff) and d['date'] not in existing]
        rows.sort(key=lambda r:r['production_date'])
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {"days": [
        {"date": r["production_date"].strftime("%Y-%m-%d"), "mixes": r["mixes_run"], "bricks": r["bricks_made"]}
        for r in rows
    ]}


@router.get("/monthly-trend")
def monthly_production_trend(months: int = 6):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cutoff = datetime.date.today() - datetime.timedelta(days=months * 31)
        cursor.execute(
            """SELECT TO_CHAR(production_date, 'YYYY-MM') AS month,
                      SUM(mixes_run) AS total_mixes, SUM(bricks_made) AS total_bricks
               FROM production_log WHERE production_date >= %s
               GROUP BY month ORDER BY month""",
            (cutoff,),
        )
        rows = cursor.fetchall()
        from historical_reporting import applied_days
        cursor.execute('SELECT production_date FROM production_log WHERE production_date >= %s',(cutoff,))
        existing={str(r['production_date']) for r in cursor.fetchall()}
        totals={r['month']:dict(r) for r in rows}
        for d in applied_days(cursor)['days']:
            if d['date'] < str(cutoff) or d['date'] in existing:continue
            month=d['date'][:7]
            r=totals.setdefault(month,dict(month=month,total_mixes=0,total_bricks=0))
            r['total_mixes']+=d['mixes'];r['total_bricks']+=d['bricks']
        rows=[totals[k] for k in sorted(totals)]
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {"months": [
        {"month": r["month"], "total_mixes": r["total_mixes"], "total_bricks": r["total_bricks"]}
        for r in rows
    ]}


# ---------------------------------------------------------
# Monthly Profit Trend (simplified, consistent standard calc —
# default selling price, full production treated as sold, no
# what-if overrides. For the detailed version use Profit Calculator.)
# ---------------------------------------------------------
@router.get('/monthly-profit-trend')
def monthly_profit_trend(months: int = 6):
    raise HTTPException(422,'Enter a selling price in the monthly profit calculator; no default price is used.')


# ---------------------------------------------------------
# Cost Breakdown (current month, per-brick, three slices)
# ---------------------------------------------------------
@router.get("/cost-breakdown")
def cost_breakdown():
    from routers.admin import production_cost_report
    r=production_cost_report()
    n=r['bricks']
    return dict(month=r['month'],material_cost_per_brick=round(r['material_cost']/n,2) if n else 0,
        making_charge_per_brick=round(r['making_cost']/n,2) if n else 0,
        overhead_per_brick=round(r['overhead']['total_overhead']/n,2) if n else 0,
        total_cost_per_brick=r['cost_per_brick'])


# ---------------------------------------------------------
# Sales Analytics
# ---------------------------------------------------------
@router.get("/sales-trend")
def sales_trend(days: int = 30):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cutoff = datetime.date.today() - datetime.timedelta(days=days - 1)
        cursor.execute(
            """SELECT sale_date, SUM(bricks_purchased) AS total_bricks, SUM(COALESCE(taxable_amount,total_amount)) AS total_revenue
               FROM brick_sales WHERE sale_date >= %s GROUP BY sale_date ORDER BY sale_date""",
            (cutoff,),
        )
        rows = cursor.fetchall()
        from historical_reporting import applied_days
        combined={str(r['sale_date']):dict(r) for r in rows}
        for d in applied_days(cursor)['days']:
            if d['date'] < str(cutoff):continue
            r=combined.setdefault(d['date'],dict(sale_date=datetime.date.fromisoformat(d['date']),total_bricks=0,total_revenue=None))
            r['total_bricks']+=sum(d['sales'])
            from services import get_text_setting
            from sales_tax import breakdown
            price=get_text_setting(cursor,'historical_sales_price_'+d['date'][:7],'')
            rate=get_text_setting(cursor,'historical_sales_gst_'+d['date'][:7],'0')
            r['total_revenue']=(float(r['total_revenue'] or 0)+sum(float(breakdown(q,price,gst_rate=rate)['taxable_amount']) for q in d['sales'])) if price else None
        rows=[combined[k] for k in sorted(combined)]
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {"days": [
        {"date": r["sale_date"].strftime("%Y-%m-%d"), "bricks_sold": r["total_bricks"], "revenue": float(r["total_revenue"]) if r["total_revenue"] is not None else None}
        for r in rows
    ]}


@router.get("/top-customers")
def top_customers(limit: int = 5):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT customer_name, customer_mobile, SUM(bricks_purchased) AS total_bricks, COUNT(*) AS total_orders
               FROM brick_sales GROUP BY customer_name, customer_mobile
               ORDER BY total_bricks DESC LIMIT %s""",
            (limit,),
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {"customers": [
        {"customer_name": r["customer_name"], "customer_mobile": r["customer_mobile"],
         "total_bricks": r["total_bricks"], "total_orders": r["total_orders"]}
        for r in rows
    ]}


# ---------------------------------------------------------
# Fun Facts
# ---------------------------------------------------------
BRICKS_PER_SMALL_HOUSE = 5000  # rough reference figure, not a precise engineering estimate


@router.get("/fun-facts")
def fun_facts():
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT COALESCE(SUM(bricks_made), 0) AS total, COUNT(*) AS days FROM production_log")
        row = cursor.fetchone()
        total_bricks_all_time = int(row["total"])
        days_worked_total = row["days"]

        cursor.execute("SELECT COALESCE(AVG(labourers_present), 0) AS avg_crew FROM production_log")
        avg_crew_size = float(cursor.fetchone()["avg_crew"])

        cursor.execute(
            "SELECT production_date, bricks_made, mixes_run FROM production_log ORDER BY bricks_made DESC LIMIT 1"
        )
        best_day_row = cursor.fetchone()

        cursor.execute("SELECT production_date FROM production_log ORDER BY production_date")
        all_dates = [r["production_date"] for r in cursor.fetchall()]

        cursor.execute(
            "SELECT COALESCE(sum(GREATEST(balance,0)),0) AS pending FROM (SELECT sum(amount) AS balance FROM customer_ledger GROUP BY customer_id) accounts"
        )
        pending_dues = float(cursor.fetchone()["pending"])

        cursor.execute("SELECT COALESCE(SUM(bricks_purchased), 0) AS total FROM brick_sales")
        total_bricks_sold_all_time = int(cursor.fetchone()["total"])

        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    # Longest consecutive-day work streak
    longest_streak = 0
    current_streak = 0
    previous_date = None
    for d in all_dates:
        if previous_date is not None and (d - previous_date).days == 1:
            current_streak += 1
        else:
            current_streak = 1
        longest_streak = max(longest_streak, current_streak)
        previous_date = d

    return {
        "total_bricks_produced_all_time": total_bricks_all_time,
        "houses_equivalent": round(total_bricks_all_time / BRICKS_PER_SMALL_HOUSE, 1),
        "days_worked_total": days_worked_total,
        "avg_crew_size": round(avg_crew_size, 1),
        "longest_work_streak_days": longest_streak,
        "best_day": {
            "date": best_day_row["production_date"].strftime("%Y-%m-%d") if best_day_row else None,
            "bricks": best_day_row["bricks_made"] if best_day_row else 0,
            "mixes": best_day_row["mixes_run"] if best_day_row else 0,
        },
        "total_bricks_sold_all_time": total_bricks_sold_all_time,
        "pending_customer_dues": round(pending_dues, 2),
    }

@router.get('/month-materials')
def month_materials(month: str = None):
    from routers.admin import production_cost_report
    from historical_reporting import applied_days
    report=production_cost_report(month)
    conn=get_connection()
    try:
        with conn.cursor() as c:
            p=applied_days(c)
            c.execute("SELECT p.production_date,p.mixes_run,s.recipe FROM production_log p LEFT JOIN production_cost_snapshots s USING(production_date) WHERE TO_CHAR(p.production_date,'YYYY-MM')=%s",(report['month'],))
            live=c.fetchall(); existing={str(r['production_date']) for r in live}
            usage={k:0.0 for k in p['recipe']}
            for d in p['days']:
                if d['date'][:7]==report['month'] and d['date'] not in existing:
                    for k,q in p['recipe'].items():usage[k]=usage.get(k,0)+q*d['mixes']
            for d in live:
                for k,q in (d['recipe'] or {}).items():usage[k]=usage.get(k,0)+float(q)*d['mixes_run']
            report['materials']={k:round(v,3) for k,v in usage.items()}
        return report
    finally:conn.close()
