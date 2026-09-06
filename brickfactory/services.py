"""
SERVICES
Shared helper functions used by BOTH admin and manager routes: recipe,
rates, charges, stock, and the bricks-per-mix setting. Same role your
original shared_data.py played — one place to change a query, instead
of five different copies scattered across files.

IMPORTANT RULE (per your requirement): everything EXCEPT rates and cost
values is a whole number — stock, mixes, bricks, labourers. Only rates
and money amounts are allowed to have decimals. These helpers enforce
that by rounding to int() wherever a quantity (not a price) is involved.
"""


def get_recipe(cursor) -> dict:
    cursor.execute("SELECT material_name, qty_per_mix FROM recipe")
    return {row["material_name"]: float(row["qty_per_mix"]) for row in cursor.fetchall()}


def get_rates(cursor, as_of=None) -> dict:
    cursor.execute(
        """SELECT DISTINCT ON (material_name) material_name, unit_rate
           FROM material_rate_versions
           WHERE effective_from <= COALESCE(%s, (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date)
           ORDER BY material_name, effective_from DESC""",
        (as_of,),
    )
    return {row["material_name"]: float(row["unit_rate"]) for row in cursor.fetchall()}


def get_charges(cursor) -> dict:
    cursor.execute("SELECT charge_name, cost_per_brick FROM making_charges")
    return {row["charge_name"]: float(row["cost_per_brick"]) for row in cursor.fetchall()}


def get_stock(cursor) -> dict:
    """Stock quantities are always whole numbers — returned as int."""
    cursor.execute("SELECT material_name, current_stock FROM materials_inventory")
    return {row["material_name"]: int(row["current_stock"]) for row in cursor.fetchall()}


def get_bricks_per_mix(cursor) -> float:
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'bricks_per_mix'")
    row = cursor.fetchone()
    return float(row["setting_value"]) if row else 182.0


def apply_stock_change_for_mixes(cursor, mixes_delta: int):
    """
    Subtracts (recipe qty * mixes_delta) from stock for every material.
    A NEGATIVE mixes_delta (a same-day correction reducing mixes) correctly
    ADDS stock back — same behavior as apply_stock_change_for_mixes() in
    your original shared_data.py.

    Every amount subtracted is rounded to a whole number BEFORE being sent
    to the database, since stock must always stay an integer.

    Must be called with a cursor already inside an open transaction —
    the caller is responsible for commit()/rollback().
    """
    cursor.execute("SELECT material_name, qty_per_mix FROM recipe")
    recipe_rows = cursor.fetchall()

    for row in recipe_rows:
        change_amount = round(float(row["qty_per_mix"]) * mixes_delta)  # whole number, can be negative
        cursor.execute(
            "UPDATE materials_inventory SET current_stock = current_stock - %s WHERE material_name = %s",
            (change_amount, row["material_name"]),
        )


# --------------------------- Outlet Brick Stock (Brick Sales feature) ---------------------------
def get_outlet_stock(cursor) -> int:
    """Current total of finished bricks available to sell at the outlet."""
    cursor.execute("SELECT total_bricks FROM outlet_stock WHERE id = 1")
    row = cursor.fetchone()
    return int(row["total_bricks"]) if row else 0


def apply_outlet_stock_change(cursor, bricks_delta: int):
    """
    Adds bricks_delta to the outlet stock total. Positive delta = bricks
    coming IN (from production). Negative delta = bricks going OUT (a sale).
    Must be called inside an open transaction — caller commits/rolls back.
    """
    cursor.execute(
        "UPDATE outlet_stock SET total_bricks = total_bricks + %s WHERE id = 1",
        (bricks_delta,),
    )


def get_default_brick_price(cursor) -> float:
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'default_cost_per_brick'")
    row = cursor.fetchone()
    return float(row["setting_value"]) if row else 7.50


# --------------------------- Text Settings (e.g. WhatsApp number) ---------------------------
# Kept in a separate table from `settings` since that one is NUMERIC-only —
# a phone number is text, never something to do math on.
def get_text_setting(cursor, key: str, default: str = "") -> str:
    cursor.execute("SELECT setting_value FROM app_settings_text WHERE setting_key = %s", (key,))
    row = cursor.fetchone()
    return row["setting_value"] if row else default


def set_text_setting(cursor, key: str, value: str):
    cursor.execute(
        """INSERT INTO app_settings_text (setting_key, setting_value) VALUES (%s, %s)
           ON CONFLICT (setting_key) DO UPDATE SET setting_value = %s""",
        (key, value, value),
    )


# --------------------------- Fixed Monthly Overhead ---------------------------
def get_monthly_overhead(cursor, target_month: str, overrides: dict = None, override_beats_actual: bool = False) -> dict:
    """
    Computes the total fixed overhead for a given month:
      Rent + Manager Salary + Electricity + Water

    Rent and Manager Salary are admin-set constants (settings table).
    Electricity/Water use the manager's ACTUAL entered bill for that month
    if one exists (utility_bills table) — otherwise fall back to the
    admin-set default. This replaces the old flawed Salary_Other
    per-brick charge everywhere it used to be factored in.

    `overrides` (optional) lets a caller do a "what-if" calculation without
    changing the stored settings.

    `override_beats_actual`: when False (default — used by the live Cost
    Per Brick calculator and the factual Overhead Report), an electricity/
    water override only fills in for a MISSING actual bill — it never
    silently replaces a real entered bill. When True (used by the Profit
    Calculator, which is explicitly a what-if scenario tool), a provided
    override wins outright, since the admin is deliberately testing a
    different number.
    """
    overrides = overrides or {}

    cursor.execute(
        "SELECT DISTINCT ON(setting_key) setting_key, amount AS setting_value FROM monthly_overhead_versions "
        "WHERE effective_month<=%s ORDER BY setting_key,effective_month DESC", (target_month,)
    )
    settings_map = {row["setting_key"]: float(row["setting_value"]) for row in cursor.fetchall()}

    rent = overrides.get("rent", settings_map.get("rent_amount", 25000.0))
    manager_salary = overrides.get("manager_salary", settings_map.get("manager_salary_amount", 30000.0))
    electricity_default = overrides.get("electricity_default", settings_map.get("electricity_default", 12000.0))
    water_default = overrides.get("water_default", settings_map.get("water_default", 6000.0))

    cursor.execute("SELECT bill_type, amount FROM utility_bills WHERE billing_month = %s", (target_month,))
    bill_rows = cursor.fetchall()
    actual_electricity = next((float(r["amount"]) for r in bill_rows if r["bill_type"] == "Electricity"), None)
    actual_water = next((float(r["amount"]) for r in bill_rows if r["bill_type"] == "Water"), None)

    if override_beats_actual and "electricity_default" in overrides:
        electricity = overrides["electricity_default"]
    else:
        electricity = actual_electricity if actual_electricity is not None else electricity_default

    if override_beats_actual and "water_default" in overrides:
        water = overrides["water_default"]
    else:
        water = actual_water if actual_water is not None else water_default

    return {
        "rent": rent,
        "manager_salary": manager_salary,
        "electricity": electricity,
        "electricity_is_default": actual_electricity is None,
        "water": water,
        "water_is_default": actual_water is None,
        "total_overhead": rent + manager_salary + electricity + water,
    }
