"""
DASHBOARD / ANALYTICS ROUTES
Read-only endpoints that power the admin Dashboard page: trend charts,
cost breakdown, sales analytics, and a few "interesting facts" pulled
from real data. Nothing here writes to the database.

To add a new dashboard widget later: add a new @router.get function here,
and a matching chart/card in frontend/js/dashboard.js.
"""

import datetime
from fastapi import APIRouter, HTTPException, Depends
from dependencies import require_admin
from database import get_connection
from services import get_recipe, get_rates, get_charges, get_bricks_per_mix, get_monthly_overhead, get_default_brick_price

router = APIRouter(prefix="/admin/dashboard", tags=["dashboard"], dependencies=[Depends(require_admin)])


# ---------------------------------------------------------
# Today's Activity — powers the "Today's Activity" card and the
# notification badge on the Dashboard sidebar button.
# ---------------------------------------------------------
@router.get("/today-activity")
def today_activity():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        today = datetime.date.today()

        cursor.execute(
            """SELECT timestamp_entered, mixes_run, bricks_made, labourers_present, misc_expense, misc_note, is_corrected
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
def _estimate_profit_for_month(cursor, target_month: str, default_price: float) -> dict:
    recipe = get_recipe(cursor)
    rates = get_rates(cursor)
    charges = get_charges(cursor)
    bricks_per_mix = get_bricks_per_mix(cursor)
    overhead = get_monthly_overhead(cursor, target_month)

    cursor.execute(
        "SELECT COALESCE(SUM(bricks_made), 0) AS total FROM production_log WHERE TO_CHAR(production_date, 'YYYY-MM') = %s",
        (target_month,),
    )
    total_bricks = int(cursor.fetchone()["total"])

    if total_bricks == 0:
        return {"month": target_month, "total_bricks": 0, "revenue": 0.0, "expenditure": round(overhead["total_overhead"], 2), "profit": round(-overhead["total_overhead"], 2)}

    material_cost_per_mix = sum(qty * rates.get(mat, 0.0) for mat, qty in recipe.items())
    material_cost_per_brick = material_cost_per_mix / bricks_per_mix
    making_charge_per_brick = sum(charges.values())

    revenue = total_bricks * default_price
    expenditure = (total_bricks * material_cost_per_brick) + (total_bricks * making_charge_per_brick) + overhead["total_overhead"]
    profit = revenue - expenditure

    return {
        "month": target_month,
        "total_bricks": total_bricks,
        "revenue": round(revenue, 2),
        "expenditure": round(expenditure, 2),
        "profit": round(profit, 2),
    }


@router.get("/monthly-profit-trend")
def monthly_profit_trend(months: int = 6):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        default_price = get_default_brick_price(cursor)

        today = datetime.date.today()
        target_months = []
        y, m = today.year, today.month
        for _ in range(months):
            target_months.append(f"{y:04d}-{m:02d}")
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        target_months.reverse()

        results = [_estimate_profit_for_month(cursor, month, default_price) for month in target_months]
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {"months": results}


# ---------------------------------------------------------
# Cost Breakdown (current month, per-brick, three slices)
# ---------------------------------------------------------
@router.get("/cost-breakdown")
def cost_breakdown():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        recipe = get_recipe(cursor)
        rates = get_rates(cursor)
        charges = get_charges(cursor)
        bricks_per_mix = get_bricks_per_mix(cursor)

        current_month = datetime.date.today().strftime("%Y-%m")
        overhead = get_monthly_overhead(cursor, current_month)
        cursor.execute(
            "SELECT COALESCE(SUM(bricks_made), 0) AS total FROM production_log WHERE TO_CHAR(production_date, 'YYYY-MM') = %s",
            (current_month,),
        )
        bricks_this_month = int(cursor.fetchone()["total"])
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    material_cost_per_mix = sum(qty * rates.get(mat, 0.0) for mat, qty in recipe.items())
    material_cost_per_brick = material_cost_per_mix / bricks_per_mix
    making_charge_per_brick = sum(charges.values())
    overhead_per_brick = (overhead["total_overhead"] / bricks_this_month) if bricks_this_month > 0 else 0.0

    return {
        "month": current_month,
        "material_cost_per_brick": round(material_cost_per_brick, 2),
        "making_charge_per_brick": round(making_charge_per_brick, 2),
        "overhead_per_brick": round(overhead_per_brick, 2),
        "total_cost_per_brick": round(material_cost_per_brick + making_charge_per_brick + overhead_per_brick, 2),
    }


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
            """SELECT sale_date, SUM(bricks_purchased) AS total_bricks, SUM(total_amount) AS total_revenue
               FROM brick_sales WHERE sale_date >= %s GROUP BY sale_date ORDER BY sale_date""",
            (cutoff,),
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {"days": [
        {"date": r["sale_date"].strftime("%Y-%m-%d"), "bricks_sold": r["total_bricks"], "revenue": float(r["total_revenue"])}
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
            "SELECT COALESCE(SUM(total_amount - amount_paid), 0) AS pending FROM brick_sales WHERE total_amount > amount_paid"
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