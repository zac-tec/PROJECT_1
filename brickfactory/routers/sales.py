"""
BRICK SALES ROUTES
Manager-facing feature: track finished bricks available at the outlet,
record customer sales against that stock, and allow same-day corrections
if a mistake is spotted — same "correction window" pattern already used
for production_log.

Outlet stock itself is NOT adjusted here when production happens — that
happens inside routers/manager.py's save_entry(), since it's tied to the
production save transaction. This file only handles SALES (stock going
OUT), not production (stock coming IN).

To add a new brick-sales-related feature later: add a function here.
"""

import datetime
from zoneinfo import ZoneInfo
from production_entry_policy import validate_entry_date
from sales_tax import breakdown, transport_total
from customer_accounts import resolve_customer, lock_account, record_sale
from batch_stock import lock_stock, stock_summary, allocate_sale, restore_sale, adjust_batches, factory_today
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from database import get_connection
from services import get_outlet_stock, apply_outlet_stock_change
from schemas import BrickSaleRequest, StockAdjustmentRequest
from pdf_generator import generate_sale_receipt
from dependencies import require_manager, get_current_user

router = APIRouter(prefix="/manager/sales", tags=["brick sales"])


# ---------------------------------------------------------
# Outlet Stock & Defaults (for pre-filling the sale form)
# ---------------------------------------------------------
@router.get("/outlet-stock", dependencies=[Depends(require_manager)])
def view_outlet_stock():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        summary = stock_summary(cursor)
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()
    return summary


@router.get("/default-price", dependencies=[Depends(require_manager)])
def view_default_price():
    return {'default_cost_per_brick': None, 'required': True}



# ---------------------------------------------------------
# Today's Sales (view + edit)
# ---------------------------------------------------------
@router.get("/today", dependencies=[Depends(require_manager)])
def view_todays_sales(date: datetime.date | None = None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        today = validate_entry_date(cursor, date)
        cursor.execute(
            """SELECT sale_id, sale_date, recorded_at, sale_timestamp, customer_name, customer_mobile, bricks_purchased,
                      cost_per_brick, amount_due, other_charges, total_amount, amount_paid, is_edited, gst_rate, taxable_amount, gst_amount, customer_id, amount_received, transport_mode, transport_rate, transport_amount
               FROM brick_sales WHERE sale_date = %s ORDER BY sale_timestamp""",
            (today,),
        )
        rows = cursor.fetchall()
        cursor.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {"sales": [
        {
            "sale_id": r["sale_id"],
            "sale_date": str(r["sale_date"]),
            "recorded_at": r["recorded_at"].isoformat() if r["recorded_at"] else None,
            "timestamp": r["sale_timestamp"].strftime("%H:%M:%S"),
            "customer_name": r["customer_name"],
            "customer_mobile": r["customer_mobile"],
            "bricks_purchased": r["bricks_purchased"],
            "cost_per_brick": float(r["cost_per_brick"]),
            "amount_due": float(r["amount_due"]),
            "other_charges": float(r["other_charges"]),
            "transport_mode": r['transport_mode'],
            "transport_rate": float(r['transport_rate'] or 0),
            "transport_amount": float(r['transport_amount'] or 0),
            "total_amount": float(r["total_amount"]),
            "amount_paid": float(r["amount_paid"]),
            "is_edited": r["is_edited"],
            "customer_id": r["customer_id"],
            "amount_received": float(r["amount_received"] or 0),
            "gst_rate": float(r["gst_rate"]) if r["gst_rate"] is not None else None,
            "taxable_amount": float(r["taxable_amount"]) if r["taxable_amount"] is not None else None,
            "gst_amount": float(r["gst_amount"]) if r["gst_amount"] is not None else None,
        }
        for r in rows
    ]}


# ---------------------------------------------------------
# Create a Sale
# ---------------------------------------------------------
@router.post("", dependencies=[Depends(require_manager)])
def create_sale(body: BrickSaleRequest, user=Depends(require_manager)):
    """
    Blocks the sale outright if bricks_purchased exceeds current outlet
    stock — the manager should always see the correct available number
    on screen before this is ever called, but this is the hard backstop.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        lock_stock(cursor)
        if body.request_id:
            cursor.execute('SELECT sale_id,sale_date,bricks_purchased,cost_per_brick,amount_received,other_charges,customer_id,transport_mode,transport_rate FROM brick_sales WHERE request_id=%s',(body.request_id,))
            previous=cursor.fetchone()
            if previous:
                if (previous['bricks_purchased']!=body.bricks_purchased or float(previous['cost_per_brick'])!=body.cost_per_brick
                    or float(previous['amount_received'])!=body.amount_paid or float(previous['other_charges'])!=body.other_charges
                    or (body.customer_id and previous['customer_id']!=body.customer_id)
                    or (body.sale_date and previous['sale_date']!=body.sale_date)
                    or (previous['transport_mode'] or 'none') != (body.transport_mode or 'none')
                    or (previous['transport_rate'] or 0) != body.transport_rate):
                    raise HTTPException(409,'This sale submission was already saved with different values. Check the selected date’s sales and clear the form before adding another sale.')
                return {'sale_id':previous['sale_id'],'message':'Sale already recorded.'}
        today = validate_entry_date(cursor, body.sale_date)
        account=resolve_customer(cursor,body.customer_name,body.customer_mobile,body.customer_id)
        current_stock = get_outlet_stock(cursor)

        transport_amount = transport_total(body.bricks_purchased,body.transport_mode,body.transport_rate)
        tax = breakdown(body.bricks_purchased,body.cost_per_brick,body.other_charges,transport_amount=transport_amount)
        amount_due, total_amount = tax["amount_due"], tax["total_amount"]

        now_time = datetime.datetime.now(ZoneInfo("Asia/Kolkata")).time()

        cursor.execute(
            """INSERT INTO brick_sales
               (sale_date, sale_timestamp, customer_name, customer_mobile, bricks_purchased,
                cost_per_brick, amount_due, other_charges, total_amount, amount_paid, is_edited)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'no')
               RETURNING sale_id""",
            (today, now_time, account["name"], account["phone"], body.bricks_purchased,
             body.cost_per_brick, amount_due, body.other_charges, total_amount, body.amount_paid),
        )
        sale_id = cursor.fetchone()["sale_id"]
        cursor.execute('UPDATE brick_sales SET customer_id=%s,amount_received=%s,request_id=%s WHERE sale_id=%s',
                       (account['customer_id'],body.amount_paid,body.request_id,sale_id))

        cursor.execute('UPDATE brick_sales SET gst_rate=%s,taxable_amount=%s,gst_amount=%s WHERE sale_id=%s',
                       (tax['gst_rate'],tax['taxable_amount'],tax['gst_amount'],sale_id))
        cursor.execute('UPDATE brick_sales SET transport_mode=%s,transport_rate=%s,transport_amount=%s WHERE sale_id=%s',
                       (body.transport_mode or 'none',body.transport_rate,transport_amount,sale_id))
        allocate_sale(cursor, sale_id, body.bricks_purchased, today)
        account_balance=record_sale(cursor,account['customer_id'],sale_id,total_amount,body.amount_paid,user['username'],today)

        conn.commit()
        cursor.close()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {
        "sale_id": sale_id,
        "amount_due": amount_due,
        "total_amount": total_amount,
        "remaining_stock": current_stock - body.bricks_purchased,
    }


# ---------------------------------------------------------
# Correct a sale within the shared entry allowance; its date stays fixed
# ---------------------------------------------------------
@router.put("/{sale_id}", dependencies=[Depends(require_manager)])
def update_sale(sale_id: int, body: BrickSaleRequest, user=Depends(require_manager)):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        lock_stock(cursor)

        cursor.execute('SELECT customer_id FROM brick_sales WHERE sale_id=%s',(sale_id,))
        identity=cursor.fetchone()
        if not identity:raise HTTPException(404,'Sale not found.')
        account=lock_account(cursor,identity['customer_id'])
        if body.customer_id and body.customer_id!=account['customer_id']:
            raise HTTPException(409,'A saved sale cannot be moved to a different customer.')
        cursor.execute("SELECT sale_date, bricks_purchased, transport_mode FROM brick_sales WHERE sale_id = %s FOR UPDATE", (sale_id,))
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Sale not found.")

        if row['transport_mode'] in ('per_brick','flat') and body.transport_mode is None:
            raise HTTPException(409, 'This sale includes transport. Reopen the updated app before correcting it.')
        today = validate_entry_date(cursor, row["sale_date"])
        if body.sale_date is not None and body.sale_date != today:
            raise HTTPException(409, 'A saved sale cannot be moved to another date. Select its original date to correct it.')

        cursor.execute('SELECT 1 FROM sale_payment_audit WHERE sale_id=%s LIMIT 1',(sale_id,))
        if cursor.fetchone():
            raise HTTPException(409, 'The admin has settled this invoice. Contact the admin before changing it.')

        cursor.execute("INSERT INTO sale_price_revision_audit(sale_id,reason,previous_record) SELECT sale_id,%s,to_jsonb(s) FROM brick_sales s WHERE sale_id=%s",('Manager dated sale/account correction',sale_id))
        restore_sale(cursor, sale_id, today)

        transport_amount = transport_total(body.bricks_purchased,body.transport_mode,body.transport_rate)
        tax = breakdown(body.bricks_purchased,body.cost_per_brick,body.other_charges,transport_amount=transport_amount)
        amount_due, total_amount = tax["amount_due"], tax["total_amount"]

        cursor.execute(
            """UPDATE brick_sales SET
                 customer_name = %s, customer_mobile = %s, bricks_purchased = %s,
                 cost_per_brick = %s, amount_due = %s, other_charges = %s,
                 total_amount = %s, amount_paid = %s, is_edited = 'yes'
               WHERE sale_id = %s""",
            (account["name"], account["phone"], body.bricks_purchased,
             body.cost_per_brick, amount_due, body.other_charges, total_amount,
             body.amount_paid, sale_id),
        )

        cursor.execute('UPDATE brick_sales SET gst_rate=%s,taxable_amount=%s,gst_amount=%s WHERE sale_id=%s',
                       (tax['gst_rate'],tax['taxable_amount'],tax['gst_amount'],sale_id))
        cursor.execute('UPDATE brick_sales SET transport_mode=%s,transport_rate=%s,transport_amount=%s WHERE sale_id=%s',
                       (body.transport_mode or 'none',body.transport_rate,transport_amount,sale_id))
        allocate_sale(cursor, sale_id, body.bricks_purchased, today)
        cursor.execute('UPDATE brick_sales SET amount_received=%s WHERE sale_id=%s',(body.amount_paid,sale_id))
        account_balance=record_sale(cursor,account['customer_id'],sale_id,total_amount,body.amount_paid,user['username'],today,replace=True)

        conn.commit()
        cursor.close()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {"sale_id": sale_id, "amount_due": amount_due, "total_amount": total_amount}


# ---------------------------------------------------------
# Manual Outlet Stock Adjustment (transfers in, returns, damage/loss)
# ---------------------------------------------------------
@router.post("/adjust-stock", dependencies=[Depends(require_manager)])
def adjust_outlet_stock(body: StockAdjustmentRequest):
    """
    Lets the manager correct outlet stock for reasons outside normal
    production/sales flow — bricks received from another outlet, customer
    returns (positive), or damage/loss (negative). Every adjustment is
    logged permanently to outlet_stock_adjustments, same audit-log pattern
    as rate_history / making_charges_history.
    """
    if body.change_amount == 0:
        raise HTTPException(status_code=400, detail="Change amount cannot be zero.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        lock_stock(cursor)
        new_total, batch_id = adjust_batches(cursor, body.change_amount, body.kind, body.batch_id, body.note)

        today = factory_today()
        now_time = datetime.datetime.now().time()
        cursor.execute(
            """INSERT INTO outlet_stock_adjustments
               (adjustment_date, adjustment_timestamp, change_amount, note, resulting_stock)
               VALUES (%s, %s, %s, %s, %s)""",
            (today, now_time, body.change_amount, f"{body.kind} · Batch #{batch_id}: {body.note}", new_total),
        )

        conn.commit()
        cursor.close()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {"change_amount": body.change_amount, "new_total": new_total}


@router.get("/stock-adjustments", dependencies=[Depends(require_manager)])
def view_stock_adjustment_history():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT adjustment_date, adjustment_timestamp, change_amount, note, resulting_stock
               FROM outlet_stock_adjustments ORDER BY adjustment_date DESC, adjustment_timestamp DESC"""
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {"adjustments": [
        {
            "date": r["adjustment_date"].strftime("%Y-%m-%d"),
            "time": r["adjustment_timestamp"].strftime("%H:%M:%S"),
            "change_amount": r["change_amount"],
            "note": r["note"],
            "resulting_stock": r["resulting_stock"],
        }
        for r in rows
    ]}


# ---------------------------------------------------------
# Sale Receipt (PDF)
# ---------------------------------------------------------
@router.get("/{sale_id}/receipt", dependencies=[Depends(get_current_user)])
def get_sale_receipt(sale_id: int):
    """Generates a printable PDF receipt for a single sale."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT sale_id, sale_date, recorded_at, sale_timestamp, customer_name, customer_mobile, bricks_purchased,
                      cost_per_brick, amount_due, other_charges, total_amount, amount_paid, is_edited, gst_rate, taxable_amount, gst_amount, customer_id, amount_received, transport_mode, transport_rate, transport_amount
               FROM brick_sales WHERE sale_id = %s""",
            (sale_id,),
        )
        row = cursor.fetchone()
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Sale not found.")

    sale = {
        "sale_id": row["sale_id"],
        "date": row["sale_date"].strftime("%Y-%m-%d"),
        "time": row["sale_timestamp"].strftime("%H:%M:%S"),
        "recorded_at": row["recorded_at"].astimezone(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y %H:%M IST") if row["recorded_at"] else None,
        "customer_name": row["customer_name"],
        "customer_mobile": row["customer_mobile"],
        "bricks_purchased": row["bricks_purchased"],
        "cost_per_brick": float(row["cost_per_brick"]),
        "amount_due": float(row["amount_due"]),
        "other_charges": float(row["other_charges"]),
        "transport_mode": row['transport_mode'],
        "transport_rate": float(row['transport_rate'] or 0),
        "transport_amount": float(row['transport_amount'] or 0),
        "total_amount": float(row["total_amount"]),
        "amount_paid": float(row["amount_paid"]),
        "is_edited": row["is_edited"],
        "gst_rate": float(row["gst_rate"]) if row["gst_rate"] is not None else None,
        "taxable_amount": float(row["taxable_amount"]) if row["taxable_amount"] is not None else None,
        "gst_amount": float(row["gst_amount"]) if row["gst_amount"] is not None else None,
    }

    pdf_bytes = generate_sale_receipt(sale)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="receipt_{sale_id}.pdf"'},
    )


# ---------------------------------------------------------
# Customer Lookup & History
# ---------------------------------------------------------
@router.get("/customers/search", dependencies=[Depends(get_current_user)])
def search_customers(q: str):
    """
    Searches by customer name OR mobile number (partial match, case
    insensitive). Returns one row per unique customer with summary
    totals — click through to /customers/{mobile} for full history.
    """
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Enter at least 2 characters to search.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        like_pattern = f"%{q.strip()}%"
        cursor.execute(
            """SELECT customer_name, customer_mobile,
                      SUM(bricks_purchased) AS total_bricks,
                      SUM(total_amount) AS total_billed,
                      SUM(amount_paid) AS total_paid,
                      COUNT(*) AS total_orders,
                      MAX(sale_date) AS last_purchase_date
               FROM brick_sales
               WHERE customer_name ILIKE %s OR customer_mobile ILIKE %s
               GROUP BY customer_name, customer_mobile
               ORDER BY last_purchase_date DESC""",
            (like_pattern, like_pattern),
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {"customers": [
        {
            "customer_name": r["customer_name"],
            "customer_mobile": r["customer_mobile"],
            "total_bricks": r["total_bricks"],
            "total_billed": round(float(r["total_billed"]), 2),
            "total_paid": round(float(r["total_paid"]), 2),
            "pending_dues": round(float(r["total_billed"]) - float(r["total_paid"]), 2),
            "total_orders": r["total_orders"],
            "last_purchase_date": r["last_purchase_date"].strftime("%Y-%m-%d"),
        }
        for r in rows
    ]}


@router.get("/customers/{mobile}/history", dependencies=[Depends(get_current_user)])
def customer_history(mobile: str):
    """Full purchase history for one customer, identified by mobile number."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT sale_id, sale_date, recorded_at, sale_timestamp, customer_name, bricks_purchased,
                      cost_per_brick, total_amount, amount_paid, is_edited, gst_rate, taxable_amount, gst_amount, customer_id, amount_received, transport_mode, transport_rate, transport_amount
               FROM brick_sales WHERE customer_mobile = %s
               ORDER BY sale_date DESC, sale_timestamp DESC""",
            (mobile,),
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No purchase history found for this mobile number.")

    total_bricks = sum(r["bricks_purchased"] for r in rows)
    total_billed = sum(float(r["total_amount"]) for r in rows)
    total_paid = sum(float(r["amount_paid"]) for r in rows)

    return {
        "customer_name": rows[0]["customer_name"],
        "customer_mobile": mobile,
        "total_orders": len(rows),
        "total_bricks": total_bricks,
        "total_billed": round(total_billed, 2),
        "total_paid": round(total_paid, 2),
        "pending_dues": round(total_billed - total_paid, 2),
        "orders": [
            {
                "sale_id": r["sale_id"],
            "sale_date": str(r["sale_date"]),
            "recorded_at": r["recorded_at"].isoformat() if r["recorded_at"] else None,
                "date": r["sale_date"].strftime("%Y-%m-%d"),
                "time": r["sale_timestamp"].strftime("%H:%M:%S"),
                "bricks_purchased": r["bricks_purchased"],
                "cost_per_brick": float(r["cost_per_brick"]),
                "total_amount": float(r["total_amount"]),
                "amount_paid": float(r["amount_paid"]),
                "balance_due": round(float(r["total_amount"]) - float(r["amount_paid"]), 2),
                "is_edited": r["is_edited"],
            "customer_id": r["customer_id"],
            "amount_received": float(r["amount_received"] or 0),
            "gst_rate": float(r["gst_rate"]) if r["gst_rate"] is not None else None,
            "taxable_amount": float(r["taxable_amount"]) if r["taxable_amount"] is not None else None,
            "gst_amount": float(r["gst_amount"]) if r["gst_amount"] is not None else None,
            }
            for r in rows
        ],
    }