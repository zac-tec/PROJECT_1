"""
ADMIN ROUTES
Everything admin_features.py did: rate management, making charges,
recipe, cost calculator, stock overview, order planning, and now (new
in this batch) the monthly reports and profit calculator.

URL paths are unchanged from before (no /admin prefix) so your existing
tests in /docs still work exactly the same.

To add a new admin feature later: add a new @router.get/post/put function
below, and a matching request model in schemas.py if it needs a body.
That's it — main.py doesn't need to change.
"""

import datetime
from batch_stock import factory_today, stock_summary
from fastapi import APIRouter, HTTPException, Depends
from dependencies import require_admin
from database import get_connection
from services import get_recipe, get_rates, get_charges, get_stock, get_bricks_per_mix, get_outlet_stock, get_monthly_overhead, get_default_brick_price
from schemas import (
    RateUpdateRequest, ChargeUpdateRequest, RecipeUpdateRequest,
    OrderRequest, ProfitCalculatorRequest, DefaultPriceUpdateRequest, FixedChargeUpdateRequest,
)

router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])


def _validate_month(month) -> str:
    """YYYY-MM format check, defaults to current month — same rule as before."""
    if not month:
        return factory_today().strftime("%Y-%m")
    try:
        if len(month) != 7:
            raise ValueError()
        datetime.date.fromisoformat(month + "-01")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid format. Please use YYYY-MM (e.g., 2026-07).")
    return month


@router.get("/reports/production-costs")
def production_cost_report(month: str = None):
    target_month = _validate_month(month)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        overhead = get_monthly_overhead(cursor, target_month)
        cursor.execute("""SELECT p.production_date, p.mixes_run, p.bricks_made,
            p.labourers_present, p.misc_expense, p.misc_note,
            c.material_cost_total, c.making_cost_total, c.snapshot_source
            FROM production_log p LEFT JOIN production_cost_snapshots c USING(production_date)
            WHERE TO_CHAR(p.production_date,'YYYY-MM')=%s ORDER BY p.production_date""", (target_month,))
        days = cursor.fetchall()
        bricks = sum(r['bricks_made'] for r in days)
        mixes = sum(r['mixes_run'] for r in days)
        missing = any(r['snapshot_source'] is None for r in days)
        material = sum(float(r['material_cost_total'] or 0) for r in days)
        making = sum(float(r['making_cost_total'] or 0) for r in days)
        misc = sum(float(r['misc_expense']) for r in days)
        total = material + making + misc + overhead['total_overhead']
        from production_metrics import average_bricks_per_mix
        return {
            'month': target_month, 'days_worked': len(days), 'bricks': bricks, 'mixes': mixes,
            'average_bricks_per_mix': average_bricks_per_mix(bricks, mixes),
            'material_cost': round(material,2), 'making_cost': round(making,2),
            'misc_expenses': round(misc,2), 'overhead': overhead,
            'total_cost': None if missing else round(total,2),
            'cost_per_brick': round(total/bricks,2) if bricks and not missing else None,
            'baseline_days': sum(r['snapshot_source']=='migration_baseline' for r in days),
            'missing_costs': missing,
            'days': [dict(r, production_date=str(r['production_date'])) for r in days],
        }
    finally:
        conn.close()


# ---------------------------------------------------------
# Rate Management
# ---------------------------------------------------------
@router.get("/rates")
def view_rates():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        today = factory_today()
        cursor.execute(
            """SELECT m.material_name, current_rate.unit_rate AS current_rate,
                      pending.unit_rate AS scheduled_rate, pending.effective_from
               FROM materials_inventory m
               LEFT JOIN LATERAL (
                 SELECT unit_rate FROM material_rate_versions
                 WHERE material_name=m.material_name AND effective_from<=%s
                 ORDER BY effective_from DESC LIMIT 1
               ) current_rate ON TRUE
               LEFT JOIN LATERAL (
                 SELECT unit_rate, effective_from FROM material_rate_versions
                 WHERE material_name=m.material_name AND effective_from>%s
                 ORDER BY effective_from LIMIT 1
               ) pending ON TRUE
               ORDER BY m.material_name""",
            (today, today),
        )
        rates = {
            row["material_name"]: {
                "current_rate": float(row["current_rate"]),
                "scheduled_rate": float(row["scheduled_rate"]) if row["scheduled_rate"] is not None else None,
                "effective_from": str(row["effective_from"]) if row["effective_from"] else None,
            }
            for row in cursor.fetchall()
        }
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()
    return rates


@router.put("/rates/{material}")
def update_rate(material: str, body: RateUpdateRequest, user: dict = Depends(require_admin)):
    from decimal import Decimal, ROUND_HALF_UP
    import math
    if not math.isfinite(body.new_rate):
        raise HTTPException(400, "Enter a finite rate.")
    new_rate = float(Decimal(str(body.new_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if not 0 < new_rate < 10000000000:
        raise HTTPException(400, "Rate must be between Rs. 0.01 and Rs. 9,999,999,999.99.")
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM materials_inventory WHERE material_name = %s FOR UPDATE", (material,))
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Unknown material '{material}'.")
        today = factory_today()
        effective_from = today + datetime.timedelta(days=1)
        old_rate = get_rates(cursor, today)[material]
        cursor.execute(
            "SELECT unit_rate FROM material_rate_versions WHERE material_name=%s AND effective_from=%s",
            (material, effective_from),
        )
        pending = cursor.fetchone()
        replaced_rate = float(pending["unit_rate"]) if pending else old_rate
        now = datetime.datetime.now()

        cursor.execute(
            """INSERT INTO material_rate_versions
               (material_name, effective_from, unit_rate, changed_at, changed_by)
               VALUES (%s,%s,%s,CURRENT_TIMESTAMP,%s)
               ON CONFLICT (material_name,effective_from) DO UPDATE SET
                 unit_rate=EXCLUDED.unit_rate, changed_at=CURRENT_TIMESTAMP,
                 changed_by=EXCLUDED.changed_by""",
            (material, effective_from, new_rate, user["username"]),
        )
        cursor.execute(
            """INSERT INTO rate_history
               (change_date, change_timestamp, material_name, old_rate, new_rate, effective_from)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (today, now, material, replaced_rate, new_rate, effective_from),
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
        "material": material, "current_rate": old_rate,
        "replaced_rate": replaced_rate if pending else None,
        "new_rate": new_rate, "effective_from": str(effective_from),
    }


@router.get("/rates/history")
def view_rate_history():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT change_timestamp, material_name, old_rate, new_rate, effective_from
               FROM rate_history ORDER BY change_timestamp"""
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    if not rows:
        return {"message": "No rate changes have been recorded yet.", "history": []}

    return {"history": [
        {
            "timestamp": r["change_timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "material": r["material_name"],
            "old_rate": float(r["old_rate"]),
            "new_rate": float(r["new_rate"]),
            "effective_from": str(r["effective_from"]) if r["effective_from"] else None,
        } for r in rows
    ]}


# ---------------------------------------------------------
# Making Charges Management
# ---------------------------------------------------------
@router.get("/charges")
def view_charges():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        charges = get_charges(cursor)
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()
    return {"charges": charges, "total_making_charge": round(sum(charges.values()), 2)}


@router.put("/charges/{charge_name}")
def update_charge(charge_name: str, body: ChargeUpdateRequest):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT cost_per_brick FROM making_charges WHERE charge_name = %s", (charge_name,))
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Unknown charge '{charge_name}'.")
        old_value = float(row["cost_per_brick"])
        now = datetime.datetime.now()

        cursor.execute(
            "UPDATE making_charges SET cost_per_brick = %s WHERE charge_name = %s",
            (body.new_value, charge_name),
        )
        cursor.execute(
            """INSERT INTO making_charges_history (change_date, change_timestamp, charge_name, old_value, new_value)
               VALUES (%s, %s, %s, %s, %s)""",
            (now.date(), now, charge_name, old_value, body.new_value),
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

    return {"charge_name": charge_name, "old_value": old_value, "new_value": body.new_value}


@router.get("/charges/history")
def view_charge_history():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT change_timestamp, charge_name, old_value, new_value FROM making_charges_history ORDER BY change_timestamp"
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    if not rows:
        return {"message": "No charge changes have been recorded yet.", "history": []}

    return {"history": [
        {
            "timestamp": r["change_timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "charge_name": r["charge_name"],
            "old_value": float(r["old_value"]),
            "new_value": float(r["new_value"]),
        } for r in rows
    ]}


# ---------------------------------------------------------
# Recipe Management
# ---------------------------------------------------------
@router.get("/recipe")
def view_recipe():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT r.material_name, r.qty_per_mix, m.unit_type
               FROM recipe r JOIN materials_inventory m ON m.material_name = r.material_name"""
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {r["material_name"]: {"qty_per_mix": float(r["qty_per_mix"]), "unit": r["unit_type"]} for r in rows}


@router.put("/recipe/{material}")
def update_recipe(material: str, body: RecipeUpdateRequest):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT qty_per_mix FROM recipe WHERE material_name = %s", (material,))
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Unknown material '{material}'.")
        old_qty = float(row["qty_per_mix"])

        cursor.execute(
            "UPDATE recipe SET qty_per_mix = %s WHERE material_name = %s",
            (body.new_qty_per_mix, material),
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

    return {"material": material, "old_qty_per_mix": old_qty, "new_qty_per_mix": body.new_qty_per_mix}


# ---------------------------------------------------------
# Cost Per Brick Calculator
# ---------------------------------------------------------
@router.get("/cost-per-brick")
def calculate_cost_per_brick():
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
        bricks_produced_this_month = int(cursor.fetchone()["total"])
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    breakdown = []
    total_material_mix_cost = 0.0
    for material, qty_per_mix in recipe.items():
        rate = rates.get(material, 0.0)
        mix_cost = qty_per_mix * rate
        total_material_mix_cost += mix_cost
        breakdown.append({
            "material": material, "qty_per_mix": qty_per_mix, "unit_rate": rate,
            "cost_per_mix": round(mix_cost, 2), "cost_per_brick": round(mix_cost / bricks_per_mix, 2),
        })

    total_material_brick_cost = total_material_mix_cost / bricks_per_mix
    total_making_charges = sum(charges.values())  # Labour + Loading + Union only (Salary_Other removed)

    # Overhead (Rent + Manager Salary + Electricity + Water) allocated per
    # brick using THIS MONTH's production so far. If nothing has been
    # produced yet this month, we can't allocate it yet — shown as 0 with
    # a note, rather than guessing.
    if bricks_produced_this_month > 0:
        overhead_per_brick = overhead["total_overhead"] / bricks_produced_this_month
        overhead_note = None
    else:
        overhead_per_brick = 0.0
        overhead_note = "No production recorded yet this month, so monthly overhead can't be allocated per brick yet."

    final_brick_cost = total_material_brick_cost + total_making_charges + overhead_per_brick

    return {
        "bricks_per_mix": bricks_per_mix,
        "materials": breakdown,
        "total_material_mix_cost": round(total_material_mix_cost, 2),
        "total_material_cost_per_brick": round(total_material_brick_cost, 2),
        "charges": charges,
        "total_making_charges": round(total_making_charges, 2),
        "monthly_overhead": {
            "month": current_month,
            "rent": overhead["rent"],
            "manager_salary": overhead["manager_salary"],
            "electricity": overhead["electricity"],
            "electricity_is_default": overhead["electricity_is_default"],
            "water": overhead["water"],
            "water_is_default": overhead["water_is_default"],
            "total_overhead": round(overhead["total_overhead"], 2),
            "bricks_produced_this_month": bricks_produced_this_month,
            "overhead_per_brick": round(overhead_per_brick, 2),
            "note": overhead_note,
        },
        "final_cost_per_brick": round(final_brick_cost, 2),
    }


# ---------------------------------------------------------
# Max Producible Bricks
# ---------------------------------------------------------
@router.get("/max-producible")
def calculate_max_producible_bricks():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        recipe = get_recipe(cursor)
        bricks_per_mix = get_bricks_per_mix(cursor)
        stock = get_stock(cursor)
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    possible_mixes_per_material = {
        material: int(stock.get(material, 0) / qty_per_mix)  # round DOWN
        for material, qty_per_mix in recipe.items()
    }
    bottleneck_material = min(possible_mixes_per_material, key=possible_mixes_per_material.get)
    max_mixes_possible = possible_mixes_per_material[bottleneck_material]
    max_bricks_possible = round(max_mixes_possible * bricks_per_mix)

    return {
        "possible_mixes_per_material": possible_mixes_per_material,
        "bottleneck_material": bottleneck_material,
        "max_mixes_possible": max_mixes_possible,
        "max_bricks_possible": max_bricks_possible,
    }


# ---------------------------------------------------------
# Stock Overview & Inventory Valuation
# ---------------------------------------------------------
@router.get("/stock-overview")
def view_stock_overview():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        recipe = get_recipe(cursor)
        rates = get_rates(cursor)
        stock = get_stock(cursor)

        cursor.execute(
            "SELECT COALESCE(SUM(mixes_run), 0) AS total_mixes, COUNT(*) AS days_worked FROM production_log"
        )
        row = cursor.fetchone()
        total_mixes, days_worked = row["total_mixes"], row["days_worked"]
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    avg_daily_mixes = (total_mixes / days_worked) if days_worked > 0 else 1.0

    materials, total_capital_value, runout_forecasts = [], 0.0, {}
    for material, qty_per_mix in recipe.items():
        stock_qty = stock.get(material, 0)
        rate = rates.get(material, 0.0)
        asset_value = stock_qty * rate
        total_capital_value += asset_value

        daily_consumption = qty_per_mix * avg_daily_mixes
        days_left = (stock_qty / daily_consumption) if daily_consumption > 0 else 0.0
        runout_forecasts[material] = days_left

        materials.append({
            "material": material, "stock_qty": stock_qty, "qty_per_mix": qty_per_mix,
            "days_left": round(days_left, 1), "unit_rate": rate, "asset_value": round(asset_value, 2),
        })

    bottleneck_material = min(runout_forecasts, key=runout_forecasts.get)

    return {
        "avg_daily_mixes": round(avg_daily_mixes, 1),
        "materials": materials,
        "total_capital_value": round(total_capital_value, 2),
        "bottleneck_material": bottleneck_material,
        "critical_days": round(runout_forecasts[bottleneck_material], 1),
    }


# ---------------------------------------------------------
# Order & Stock Planning
# ---------------------------------------------------------
@router.post("/order-planning")
def calculate_order_materials(body: OrderRequest):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        recipe = get_recipe(cursor)
        bricks_per_mix = get_bricks_per_mix(cursor)
        stock = get_stock(cursor)
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    mixes_needed = body.order_bricks / bricks_per_mix
    # A positive order always needs AT LEAST one full mix run — a mix can't
    # be partially run, so round() alone could wrongly show 0 mixes (and
    # therefore 0 material needed) for small orders. Enforce a floor of 1.
    whole_mixes_needed = max(1, round(mixes_needed))

    materials = []
    for material, qty_per_mix in recipe.items():
        needed = round(qty_per_mix * whole_mixes_needed)
        in_stock = stock.get(material, 0)
        deficit = needed - in_stock
        materials.append({
            "material": material, "needed": needed, "in_stock": in_stock,
            "deficit": deficit if deficit > 0 else 0, "sufficient": deficit <= 0,
        })

    note = None
    if mixes_needed < 1:
        note = f"This order is less than one full mix ({bricks_per_mix} bricks) — 1 mix is enough to cover it."

    return {
        "order_bricks": body.order_bricks,
        "exact_mixes_needed": round(mixes_needed, 2),
        "whole_mixes_needed": whole_mixes_needed,
        "note": note,
        "materials": materials,
    }


# ---------------------------------------------------------
# Monthly Overhead Report (NEW in this batch)
# ---------------------------------------------------------
@router.get("/reports/overhead")
def view_monthly_overhead_report(month: str = None):
    target_month = _validate_month(month)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        overhead = get_monthly_overhead(cursor, target_month)

        cursor.execute(
            "SELECT COALESCE(SUM(bricks_made), 0) AS total FROM production_log WHERE TO_CHAR(production_date, 'YYYY-MM') = %s",
            (target_month,),
        )
        total_bricks_produced = int(cursor.fetchone()["total"])
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    overhead_per_brick = (overhead["total_overhead"] / total_bricks_produced) if total_bricks_produced > 0 else 0.0

    return {
        "month": target_month,
        "rent": overhead["rent"],
        "manager_salary": overhead["manager_salary"],
        "electricity": overhead["electricity"],
        "electricity_is_default": overhead["electricity_is_default"],
        "water": overhead["water"],
        "water_is_default": overhead["water_is_default"],
        "total_overhead": round(overhead["total_overhead"], 2),
        "total_bricks_produced": total_bricks_produced,
        "overhead_per_brick": round(overhead_per_brick, 2),
    }


# ---------------------------------------------------------
# Monthly Production Report (NEW in this batch)
# ---------------------------------------------------------
@router.get("/reports/production")
def view_production_report(month: str = None):
    target_month = _validate_month(month)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT production_date, mixes_run, bricks_made, labourers_present, misc_expense, misc_note
               FROM production_log WHERE TO_CHAR(production_date, 'YYYY-MM') = %s ORDER BY production_date""",
            (target_month,),
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    if not rows:
        return {"month": target_month, "message": f"No production records found for the period: {target_month}"}

    total_mixes = sum(r["mixes_run"] for r in rows)
    total_bricks = sum(r["bricks_made"] for r in rows)
    total_labourers = sum(r["labourers_present"] for r in rows)
    days_worked = len(rows)

    misc_notes, total_misc_charges = [], 0.0
    for r in rows:
        misc_amount = float(r["misc_expense"])
        if misc_amount > 0:
            total_misc_charges += misc_amount
            misc_notes.append({"amount": misc_amount, "note": r["misc_note"], "date": r["production_date"].strftime("%Y-%m-%d")})

    return {
        "month": target_month,
        "days_worked": days_worked,
        "total_mixes": total_mixes,
        "total_bricks": total_bricks,
        "avg_bricks_per_mix": round(total_bricks / total_mixes, 2) if total_mixes > 0 else 0.0,
        "total_labourers": total_labourers,
        "avg_labourers_per_day": round(total_labourers / days_worked, 1),
        "total_misc_charges": round(total_misc_charges, 2),
        "misc_notes": misc_notes,
    }


# ---------------------------------------------------------
# Profit & Loss Calculator (NEW in this batch)
# ---------------------------------------------------------
@router.post("/profit-calculator")
def calculate_monthly_profit(body: ProfitCalculatorRequest):
    target_month = _validate_month(body.month)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        recipe = get_recipe(cursor)
        rates = get_rates(cursor)
        charges = get_charges(cursor)  # Labour + Loading + Union only (Salary_Other removed)
        bricks_per_mix = get_bricks_per_mix(cursor)
        default_selling_price = get_default_brick_price(cursor)

        overrides = {
            "rent": body.rent_override,
            "manager_salary": body.manager_salary_override,
            "electricity_default": body.electricity_default_override,
            "water_default": body.water_default_override,
        }
        overrides = {k: v for k, v in overrides.items() if v is not None}
        overhead = get_monthly_overhead(cursor, target_month, overrides, override_beats_actual=True)

        cursor.execute(
            """SELECT COALESCE(SUM(bricks_made), 0) AS total_bricks, COALESCE(SUM(misc_expense), 0) AS total_misc
               FROM production_log WHERE TO_CHAR(production_date, 'YYYY-MM') = %s""",
            (target_month,),
        )
        prod_row = cursor.fetchone()
        total_bricks_produced = int(prod_row["total_bricks"])
        total_misc_leakages = float(prod_row["total_misc"])
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    selling_price = body.selling_price if body.selling_price is not None else default_selling_price
    bricks_sold = total_bricks_produced if body.bricks_sold is None else body.bricks_sold

    material_cost_per_mix = sum(qty * rates.get(mat, 0.0) for mat, qty in recipe.items())
    material_cost_per_brick = material_cost_per_mix / bricks_per_mix
    making_charge_per_brick = sum(charges.values())
    base_cost_per_brick = material_cost_per_brick + making_charge_per_brick

    gross_revenue = bricks_sold * selling_price

    result = {
        "month": target_month,
        "bricks_sold": bricks_sold,
        "selling_price": selling_price,
        "selling_price_was_defaulted": body.selling_price is None,
        "gross_revenue": round(gross_revenue, 2),
        "total_misc_leakages": round(total_misc_leakages, 2),
        "used_live_config_fallback": total_bricks_produced == 0,
        # Fixed monthly overhead breakdown — shown so the frontend can
        # display these as editable "what-if" fields for the admin.
        "overhead": {
            "rent": overhead["rent"],
            "manager_salary": overhead["manager_salary"],
            "electricity": overhead["electricity"],
            "electricity_is_default": overhead["electricity_is_default"],
            "water": overhead["water"],
            "water_is_default": overhead["water_is_default"],
            "total_overhead": round(overhead["total_overhead"], 2),
        },
    }

    if total_bricks_produced == 0:
        simulated_cost = bricks_sold * base_cost_per_brick
        total_expenditures = simulated_cost + overhead["total_overhead"] + total_misc_leakages
        result["cost_of_bricks_sold"] = round(simulated_cost, 2)
        result["base_cost_per_brick"] = round(base_cost_per_brick, 2)
    else:
        total_material_expense = bricks_sold * material_cost_per_brick
        total_making_expense = bricks_sold * making_charge_per_brick
        total_expenditures = total_material_expense + total_making_expense + overhead["total_overhead"] + total_misc_leakages
        result["raw_materials_cost"] = round(total_material_expense, 2)
        result["material_cost_per_brick"] = round(material_cost_per_brick, 2)
        result["fixed_making_charges"] = round(total_making_expense, 2)
        result["making_charge_per_brick"] = round(making_charge_per_brick, 2)

    net_profit = gross_revenue - total_expenditures
    result["total_expenditures"] = round(total_expenditures, 2)
    result["net_profit"] = round(net_profit, 2)
    result["is_profit"] = net_profit >= 0
    result["profit_margin_pct"] = round((net_profit / gross_revenue) * 100, 2) if gross_revenue > 0 else 0.0

    return result


# ---------------------------------------------------------
# Default Brick Sale Price (NEW — supports the Brick Sales feature)
# ---------------------------------------------------------
@router.get("/default-brick-price")
def view_default_brick_price():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'default_cost_per_brick'")
        row = cursor.fetchone()
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {"default_cost_per_brick": float(row["setting_value"]) if row else 7.50}


@router.put("/default-brick-price")
def update_default_brick_price(body: DefaultPriceUpdateRequest):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'default_cost_per_brick'")
        row = cursor.fetchone()
        old_value = float(row["setting_value"]) if row else 7.50

        cursor.execute(
            """INSERT INTO settings (setting_key, setting_value) VALUES ('default_cost_per_brick', %s)
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

    return {"old_value": old_value, "new_value": body.new_value}


# ---------------------------------------------------------
# Brick Sales — Admin View (outlet stock, full transaction list, monthly summary)
# ---------------------------------------------------------
@router.get("/brick-sales/outlet-stock")
def view_outlet_stock_admin():
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


@router.get("/brick-sales")
def view_all_brick_sales():
    """Full transaction list, most recent first — the frontend scrolls this."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT sale_id, sale_date, sale_timestamp, customer_name, customer_mobile, bricks_purchased,
                      cost_per_brick, amount_due, other_charges, total_amount, amount_paid, is_edited
               FROM brick_sales ORDER BY sale_date DESC, sale_timestamp DESC"""
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {"sales": [
        {
            "sale_id": r["sale_id"],
            "date": r["sale_date"].strftime("%Y-%m-%d"),
            "time": r["sale_timestamp"].strftime("%H:%M:%S"),
            "customer_name": r["customer_name"],
            "customer_mobile": r["customer_mobile"],
            "bricks_purchased": r["bricks_purchased"],
            "cost_per_brick": float(r["cost_per_brick"]),
            "amount_due": float(r["amount_due"]),
            "other_charges": float(r["other_charges"]),
            "total_amount": float(r["total_amount"]),
            "amount_paid": float(r["amount_paid"]),
            "is_edited": r["is_edited"],
        }
        for r in rows
    ]}


@router.get("/brick-sales/monthly-summary")
def view_monthly_brick_sales_summary(month: str = None):
    target_month = _validate_month(month)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT COALESCE(SUM(bricks_purchased), 0) AS total_bricks,
                      COALESCE(SUM(total_amount), 0) AS total_revenue,
                      COALESCE(SUM(amount_paid), 0) AS total_collected,
                      COUNT(*) AS total_sales
               FROM brick_sales WHERE TO_CHAR(sale_date, 'YYYY-MM') = %s""",
            (target_month,),
        )
        row = cursor.fetchone()
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {
        "month": target_month,
        "total_bricks_sold": int(row["total_bricks"]),
        "total_revenue": round(float(row["total_revenue"]), 2),
        "total_collected": round(float(row["total_collected"]), 2),
        "total_sales_count": row["total_sales"],
    }


# ---------------------------------------------------------
# Fixed Monthly Charges (Rent, Manager Salary, Electricity/Water defaults)
# Replaces the old flawed Salary_Other per-brick charge.
# ---------------------------------------------------------
FIXED_CHARGE_KEYS = {
    "rent_amount": "Rent",
    "manager_salary_amount": "Manager Salary",
    "electricity_default": "Electricity Default",
    "water_default": "Water Default",
}


@router.get("/fixed-monthly-charges")
def view_fixed_monthly_charges():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT setting_key, setting_value FROM settings WHERE setting_key = ANY(%s)",
            (list(FIXED_CHARGE_KEYS.keys()),),
        )
        rows = {r["setting_key"]: float(r["setting_value"]) for r in cursor.fetchall()}
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {
        key: {"label": label, "value": rows.get(key, 0.0)}
        for key, label in FIXED_CHARGE_KEYS.items()
    }


@router.put("/fixed-monthly-charges/{key}")
def update_fixed_monthly_charge(key: str, body: FixedChargeUpdateRequest):
    if key not in FIXED_CHARGE_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown fixed charge key '{key}'.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT setting_value FROM settings WHERE setting_key = %s", (key,))
        row = cursor.fetchone()
        old_value = float(row["setting_value"]) if row else 0.0

        cursor.execute(
            """INSERT INTO settings (setting_key, setting_value) VALUES (%s, %s)
               ON CONFLICT (setting_key) DO UPDATE SET setting_value = %s""",
            (key, body.new_value, body.new_value),
        )
        cursor.execute(
            """INSERT INTO monthly_overhead_versions(setting_key,effective_month,amount)
               VALUES (%s,%s,%s) ON CONFLICT(setting_key,effective_month)
               DO UPDATE SET amount=EXCLUDED.amount""",
            (key, factory_today().strftime('%Y-%m'), body.new_value),
        )
        conn.commit()
        cursor.close()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {"key": key, "label": FIXED_CHARGE_KEYS[key], "old_value": old_value, "new_value": body.new_value}
