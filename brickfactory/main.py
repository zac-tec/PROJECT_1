"""
MAIN
The app entrypoint. This file stays short on purpose — it only wires
things together. All actual logic lives in routers/admin.py and
routers/manager.py, matching how your original program split into
admin_features.py and manager_features.py.

HOW TO ADD A NEW FEATURE LATER:
  - Admin feature   -> add a function to routers/admin.py
  - Manager feature -> add a function to routers/manager.py
  - New request body needed -> add a model to schemas.py
  - New shared query needed by both -> add a function to services.py
  This file (main.py) does NOT need to change for any of that.

Run with:
    uvicorn main:app --reload

Interactive docs:
    http://100.79.141.101:8000/docs
"""

from fastapi import FastAPI, HTTPException, Depends
from http_security import install_http_security
from dependencies import get_current_user
from database import get_connection
from services import get_stock
from routers import admin, manager, auth, sales, dashboard, daily_report
import scheduler

app = FastAPI(title="Brick Factory API")

# Browser access is restricted to the configured deployment origins.
install_http_security(app)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(manager.router)
app.include_router(sales.router)
app.include_router(dashboard.router)
app.include_router(daily_report.router)


@app.on_event("startup")
def _start_background_scheduler():
    """
    Starts the daily auto-email job. Wrapped in try/except so a fresh
    database that hasn't had migration_delivery_settings.sql run yet
    doesn't crash the whole app on startup — it just skips scheduling
    and logs a warning instead.
    """
    from batch_stock import initialize_batches
    initialize_batches()
    from cost_history import initialize_cost_history
    from pathlib import Path
    connection = get_connection()
    try:
        connection.cursor().execute(Path(__file__).with_name("migration_material_rates.sql").read_text())
        connection.commit()
    finally:
        connection.close()
    initialize_cost_history()
    try:
        scheduler.start_scheduler()
    except Exception as e:
        print(f"[startup] Could not start the daily report scheduler (has migration_delivery_settings.sql been run?): {e}")


@app.get("/")
def root():
    return {"message": "Brick Factory API is running.", "try": ["/health", "/stock", "/docs"]}


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "FastAPI is running"}


@app.get("/stock", dependencies=[Depends(get_current_user)])
def view_stock():
    """
    Shared stock view (both admin and manager use this). Kept at the
    root level since it's not exclusive to one role. Manager also has
    a namespaced copy at /manager/stock for consistency with its other
    routes — same data either way.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        stock = get_stock(cursor)
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    units = {"Flyash": "kg", "Sand": "kg", "Chemical": "L", "Cement": "packets"}
    return {m: {"quantity": qty, "unit": units.get(m, "")} for m, qty in stock.items()}