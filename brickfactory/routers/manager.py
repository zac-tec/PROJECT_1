"""
MANAGER ROUTES
Everything manager_features.py did: viewing/refilling stock, adjusting
the bricks-per-mix setting, entering today's production (with the same
auto-calculate + same-day-correction + stock-shortfall-check logic as
the original save_entry()), and logging utility bills.

All routes are grouped under /manager so it's obvious at a glance which
role a URL belongs to. To add a new manager feature later: add a new
@router function below, and a request model in schemas.py if needed.

STRICT INTEGER RULE: stock, mixes, bricks, and labourers are always
whole numbers. Only misc_amount and utility bill amounts (money) are
allowed to be decimals.
"""

import datetime
import json
from batch_stock import lock_stock, production_change, factory_today
from cost_history import capture_production_cost, production_cost_context
from production_metrics import average_bricks_per_mix
from fastapi import APIRouter, HTTPException, Depends
from dependencies import require_manager
from database import get_connection
from services import get_stock, get_bricks_per_mix, apply_stock_change_for_mixes, apply_outlet_stock_change
from schemas import (
    StockRefillRequest, BricksPerMixUpdateRequest,
    ProductionPreviewRequest, ProductionSaveRequest, UtilityBillRequest,
)

router = APIRouter(prefix="/manager", tags=["manager"], dependencies=[Depends(require_manager)])

STOCK_UNITS = {"Flyash": "kg", "Sand": "kg", "Chemical": "L", "Cement": "packets"}


# ---------------------------------------------------------
# Stock (view + refill)
# ---------------------------------------------------------
@router.get("/stock")
def view_stock():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        stock = get_stock(cursor)
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {m: {"quantity": qty, "unit": STOCK_UNITS.get(m, "")} for m, qty in stock.items()}


@router.post("/stock/refill")
def add_stock_refill(body: StockRefillRequest, user: dict = Depends(require_manager)):
    """
    Same entry-unit conversion as add_stock_refill() in the original:
    Flyash/Sand entered in TONS -> converted to kg (x1000).
    Chemical entered in LITRES, Cement in PACKETS -> no conversion.
    Result is always a whole number added to current_stock.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        stock = get_stock(cursor)

        if body.material not in stock:
            raise HTTPException(status_code=404, detail=f"Unknown material '{body.material}'.")

        if body.material in ("Flyash", "Sand"):
            quantity_received = body.amount * 1000
        else:
            quantity_received = body.amount

        cursor.execute(
            "UPDATE materials_inventory SET current_stock = current_stock + %s WHERE material_name = %s RETURNING current_stock",
            (quantity_received, body.material),
        )
        new_total = cursor.fetchone()["current_stock"]
        cursor.execute(
            "INSERT INTO factory_activity_events (actor, event_type, details) VALUES (%s, 'material_refill', %s::jsonb)",
            (user["username"], json.dumps({"material": body.material, "added": quantity_received,
             "unit": STOCK_UNITS.get(body.material, ""), "new_total": new_total})),
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

    return {
        "material": body.material,
        "added": quantity_received,
        "unit": STOCK_UNITS.get(body.material, ""),
        "new_total": new_total,
    }


# ---------------------------------------------------------
# Bricks Per Mix Setting
# ---------------------------------------------------------
@router.get("/bricks-per-mix")
def view_bricks_per_mix():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        value = get_bricks_per_mix(cursor)
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()
    return {"bricks_per_mix": value}


@router.put("/bricks-per-mix")
def update_bricks_per_mix(body: BricksPerMixUpdateRequest):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        current_value = get_bricks_per_mix(cursor)

        cursor.execute(
            """INSERT INTO settings (setting_key, setting_value) VALUES ('bricks_per_mix', %s)
               ON CONFLICT (setting_key) DO UPDATE SET setting_value = %s""",
            (body.new_value, body.new_value),
        )
        conn.commit()
        cursor.close()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {"old_value": current_value, "new_value": body.new_value}


# ---------------------------------------------------------
# Daily Production Entry
# ---------------------------------------------------------
@router.post("/production/preview")
def preview_today_entry(body: ProductionPreviewRequest):
    """
    Same auto-calculation rule as enter_today_data() in the original:
    - both given -> trusted as-is
    - one blank -> the other is CALCULATED from bricks_per_mix, using round()
    - both blank -> error
    Result is not saved yet — the frontend shows this as a draft first.
    """
    if body.mixes is None and body.bricks_produced is None:
        raise HTTPException(status_code=400, detail="You must enter at least one of mixes or bricks.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        bricks_per_mix = get_bricks_per_mix(cursor)
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    if body.mixes is None:
        bricks_produced = body.bricks_produced
        mixes = round(bricks_produced / bricks_per_mix)
        calculated_field = "mixes"
    elif body.bricks_produced is None:
        mixes = body.mixes
        bricks_produced = round(mixes * bricks_per_mix)
        calculated_field = "bricks"
    else:
        mixes = body.mixes
        bricks_produced = body.bricks_produced
        calculated_field = "none"

    return {"mixes": mixes, "bricks_produced": bricks_produced, "calculated_field": calculated_field,
            "avg_bricks_per_mix": average_bricks_per_mix(bricks_produced, mixes)}


@router.get("/production/today")
def get_todays_entry():
    """Lets the frontend check if today already has a saved entry before showing the form."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        today = datetime.date.today()
        cursor.execute(
            """SELECT timestamp_entered, mixes_run, bricks_made, labourers_present, misc_expense, misc_note, is_corrected
               FROM production_log WHERE production_date = %s""",
            (today,),
        )
        row = cursor.fetchone()
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    if row is None:
        return {"exists": False}

    return {
        "exists": True,
        "timestamp": row["timestamp_entered"].strftime("%H:%M:%S"),
        "mixes": row["mixes_run"],
        "bricks_produced": row["bricks_made"],
        "labourers": row["labourers_present"],
        "misc_amount": float(row["misc_expense"]),
        "misc_note": row["misc_note"],
        "is_corrected": row["is_corrected"],
    }


@router.post("/production/save")
def save_entry(body: ProductionSaveRequest):
    """
    Mirrors save_entry() from manager_features.py exactly:
      1. Look for an existing row for today.
      2. If found, require confirm_overwrite=True and compute
         mixes_delta = new mixes - old mixes.
      3. If mixes_delta > 0, check every recipe material has enough stock
         BEFORE writing anything — reject with a shortfall list if not.
      4. If correcting, delete the old row and mark is_corrected='yes'.
      5. Insert the new row and apply the stock delta (a downward
         correction correctly ADDS stock back).
    Everything happens in one transaction so a failure never leaves
    stock and the log out of sync.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        lock_stock(cursor)
        today = factory_today()
        now_time = datetime.datetime.now().time()

        cursor.execute(
            "SELECT timestamp_entered, mixes_run, bricks_made FROM production_log WHERE production_date = %s", (today,)
        )
        existing = cursor.fetchone()

        mixes_delta = body.mixes
        bricks_delta = body.bricks_produced
        is_correction = False

        if existing is not None:
            if not body.confirm_overwrite:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"An entry for {today} already exists (saved at {existing['timestamp_entered'].strftime('%H:%M:%S')}). "
                        "Resend with confirm_overwrite=true to replace it."
                    ),
                )
            is_correction = True
            mixes_delta = body.mixes - existing["mixes_run"]
            bricks_delta = body.bricks_produced - existing["bricks_made"]

        context = production_cost_context(cursor, today)
        old_mixes = existing['mixes_run'] if existing else 0
        material_deltas = {m: round(float(qty) * body.mixes) - round(float(qty) * old_mixes)
                           for m, qty in context['recipe'].items()}
        if mixes_delta > 0:
            stock = get_stock(cursor)

            shortfalls = []
            for material, required in material_deltas.items():
                available = stock.get(material, 0)
                if required > available:
                    shortfalls.append({
                        "material": material, "required": required,
                        "available": available, "short_by": required - available,
                    })

            if shortfalls:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": f"Not enough stock to save this entry ({mixes_delta} mix(es) worth needed).",
                        "shortfalls": shortfalls,
                    },
                )

        if is_correction:
            cursor.execute("INSERT INTO production_revision_history(production_date, previous_record) SELECT production_date,to_jsonb(p) FROM production_log p WHERE production_date=%s", (today,))

        cursor.execute(
            """INSERT INTO production_log
               (production_date, timestamp_entered, mixes_run, bricks_made, calculated_field,
                labourers_present, misc_expense, misc_note, is_corrected)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT(production_date) DO UPDATE SET
                timestamp_entered=EXCLUDED.timestamp_entered, mixes_run=EXCLUDED.mixes_run,
                bricks_made=EXCLUDED.bricks_made, calculated_field=EXCLUDED.calculated_field,
                labourers_present=EXCLUDED.labourers_present, misc_expense=EXCLUDED.misc_expense,
                misc_note=EXCLUDED.misc_note, is_corrected=EXCLUDED.is_corrected""",
            (today, now_time, body.mixes, body.bricks_produced, body.calculated_field,
             body.labourers, body.misc_amount, body.misc_note, "yes" if is_correction else "no"),
        )

        for material, quantity in material_deltas.items():
            cursor.execute("UPDATE materials_inventory SET current_stock=current_stock-%s WHERE material_name=%s", (quantity, material))
        production_change(cursor, today, bricks_delta)
        capture_production_cost(cursor, today, body.mixes, body.bricks_produced, context)

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
        "message": f"Entry saved for {today}.",
        "mixes_delta_applied": mixes_delta,
        "bricks_delta_applied": bricks_delta,
        "is_correction": is_correction,
    }


# ---------------------------------------------------------
# Utility Bills
# ---------------------------------------------------------
@router.post("/utility-bills")
def enter_utility_bill(body: UtilityBillRequest, user: dict = Depends(require_manager)):
    if body.bill_type not in ("Electricity", "Water"):
        raise HTTPException(status_code=400, detail="bill_type must be 'Electricity' or 'Water'.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        today = datetime.date.today()
        current_month = body.billing_month or today.strftime("%Y-%m")
        try:
            datetime.datetime.strptime(current_month, "%Y-%m")
        except ValueError:
            raise HTTPException(status_code=422, detail="Choose a valid billing month.")
        now_time = datetime.datetime.now().time()

        cursor.execute(
            "SELECT amount, entry_date, entry_timestamp FROM utility_bills WHERE billing_month = %s AND bill_type = %s",
            (current_month, body.bill_type),
        )
        existing = cursor.fetchone()

        if existing is not None and not body.confirm_overwrite:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"A {body.bill_type} bill of Rs.{float(existing['amount']):.2f} already exists for {current_month} "
                    f"(logged on {existing['entry_date']} at {existing['entry_timestamp'].strftime('%H:%M:%S')}). "
                    "Resend with confirm_overwrite=true to replace it."
                ),
            )

        cursor.execute(
            """INSERT INTO utility_bills (billing_month, bill_type, amount, entry_date, entry_timestamp)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (billing_month, bill_type)
               DO UPDATE SET amount = %s, entry_date = %s, entry_timestamp = %s""",
            (current_month, body.bill_type, body.amount, today, now_time,
             body.amount, today, now_time),
        )
        cursor.execute(
            "INSERT INTO factory_activity_events (actor, event_type, details) VALUES (%s, 'utility_bill', %s::jsonb)",
            (user["username"], json.dumps({"bill_type": body.bill_type, "month": current_month,
             "amount": body.amount, "previous_amount": float(existing["amount"]) if existing else None})),
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

    return {
        "bill_type": body.bill_type,
        "month": current_month,
        "amount": body.amount,
        "was_correction": existing is not None,
    }

@router.get("/utility-bills")
def view_utility_bills(month: str = None):
    month = month or datetime.date.today().strftime("%Y-%m")
    try:
        datetime.datetime.strptime(month, "%Y-%m")
    except ValueError:
        raise HTTPException(status_code=422, detail="Choose a valid billing month.")
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT bill_type, amount, entry_date, entry_timestamp FROM utility_bills WHERE billing_month = %s ORDER BY bill_type", (month,))
            return {"month": month, "bills": [{"bill_type": row["bill_type"], "amount": float(row["amount"]), "entry_date": str(row["entry_date"]), "entry_time": str(row["entry_timestamp"])} for row in cursor.fetchall()]}
    finally:
        conn.close()
