"""
DAILY REPORT ROUTES
Powers the "Share Daily Report" button: pulls together today's stock,
production, and sales into one PDF, plus a plain-text summary formatted
for pasting straight into WhatsApp.

This does NOT send anything automatically — see the frontend for the
one-tap share flow (wa.me link for text, native share sheet for the PDF).
True unattended auto-sending would need the Meta/Twilio WhatsApp Business
API, which we deliberately did not build yet (see chat discussion).
"""

import datetime
from batch_stock import stock_summary
from production_metrics import average_bricks_per_mix
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from database import get_connection
from services import get_stock, get_text_setting, set_text_setting
from schemas import WhatsAppNumberUpdateRequest, EmailUpdateRequest, ScheduleUpdateRequest
from pdf_generator import generate_daily_report
from email_sender import send_daily_report_email
from dependencies import require_admin, get_current_user

router = APIRouter(prefix="/daily-report", tags=["daily report"])

STOCK_UNITS = {"Flyash": "kg", "Sand": "kg", "Chemical": "L", "Cement": "packets"}


def _gather_daily_report_data(cursor, target_date: datetime.date) -> dict:
    stock = get_stock(cursor)
    stock_display = {m: {"qty": qty, "unit": STOCK_UNITS.get(m, "")} for m, qty in stock.items()}

    finished_bricks = stock_summary(cursor)

    cursor.execute(
        """SELECT mixes_run, bricks_made, labourers_present, misc_expense, misc_note, calculated_field
           FROM production_log WHERE production_date = %s""",
        (target_date,),
    )
    prod_row = cursor.fetchone()
    production = None
    if prod_row is not None:
        production = {
            "mixes": prod_row["mixes_run"],
            "avg_bricks_per_mix": average_bricks_per_mix(prod_row["bricks_made"], prod_row["mixes_run"]),
            "average_is_estimated": prod_row["calculated_field"] != "none",
            "bricks_produced": prod_row["bricks_made"],
            "labourers": prod_row["labourers_present"],
            "misc_amount": float(prod_row["misc_expense"]),
            "misc_note": prod_row["misc_note"],
        }

    cursor.execute(
        """SELECT COUNT(*) AS count, COALESCE(SUM(bricks_purchased), 0) AS total_bricks,
                  COALESCE(SUM(total_amount), 0) AS total_revenue, COALESCE(SUM(amount_paid), 0) AS total_paid
           FROM brick_sales WHERE sale_date = %s""",
        (target_date,),
    )
    sales_row = cursor.fetchone()
    sales = {
        "count": sales_row["count"],
        "total_bricks": sales_row["total_bricks"],
        "total_revenue": round(float(sales_row["total_revenue"]), 2),
        "total_paid": round(float(sales_row["total_paid"]), 2),
    }

    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "production": production,
        "stock": stock_display,
        "outlet_stock": finished_bricks["total_bricks"],
        "finished_bricks": finished_bricks,
        "sales": sales,
    }


# ---------------------------------------------------------
# Client WhatsApp Number (admin-configurable)
# ---------------------------------------------------------
@router.get("/whatsapp-number", dependencies=[Depends(require_admin)])
def view_whatsapp_number():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        number = get_text_setting(cursor, "client_whatsapp_number", "")
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()
    return {"number": number}


@router.put("/whatsapp-number", dependencies=[Depends(require_admin)])
def update_whatsapp_number(body: WhatsAppNumberUpdateRequest):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        set_text_setting(cursor, "client_whatsapp_number", body.number.strip())
        conn.commit()
        cursor.close()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()
    return {"number": body.number.strip()}


# ---------------------------------------------------------
# Client Email (admin-configurable)
# ---------------------------------------------------------
@router.put("/email", dependencies=[Depends(require_admin)])
def update_client_email(body: EmailUpdateRequest):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        set_text_setting(cursor, "client_email", body.email.strip())
        conn.commit()
        cursor.close()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()
    return {"email": body.email.strip()}


# ---------------------------------------------------------
# Auto-send Schedule (admin-configurable)
# ---------------------------------------------------------
@router.put("/schedule", dependencies=[Depends(require_admin)])
def update_schedule(body: ScheduleUpdateRequest):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        set_text_setting(cursor, "daily_send_time", body.send_time)
        set_text_setting(cursor, "daily_send_enabled", "true" if body.enabled else "false")
        conn.commit()
        cursor.close()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    # Reschedule the background job to the new time immediately, so a
    # changed time takes effect without needing a server restart.
    from scheduler import reschedule
    try:
        reschedule(body.send_time)
    except Exception as e:
        # The setting saved fine even if rescheduling has an issue —
        # worst case it uses the old time until the server restarts.
        print(f"[daily_report] Warning: could not reschedule job: {e}")

    return {"send_time": body.send_time, "enabled": body.enabled}


# ---------------------------------------------------------
# Combined Delivery Settings (one call for the merged settings panel)
# ---------------------------------------------------------
@router.get("/delivery-settings", dependencies=[Depends(require_admin)])
def view_delivery_settings():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        whatsapp_number = get_text_setting(cursor, "client_whatsapp_number", "")
        email = get_text_setting(cursor, "client_email", "")
        send_time = get_text_setting(cursor, "daily_send_time", "20:00")
        enabled = get_text_setting(cursor, "daily_send_enabled", "false") == "true"
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    return {
        "whatsapp_number": whatsapp_number,
        "email": email,
        "send_time": send_time,
        "auto_send_enabled": enabled,
    }


# ---------------------------------------------------------
# Send Email Now (on-demand)
# ---------------------------------------------------------
@router.post("/send-email-now", dependencies=[Depends(require_admin)])
def send_email_now():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        recipient = get_text_setting(cursor, "client_email", "")
        data = _gather_daily_report_data(cursor, datetime.date.today())
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    try:
        pdf_bytes = generate_daily_report(data)
        send_daily_report_email(recipient, pdf_bytes, data["date"], data["production"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": f"Report emailed to {recipient}."}


# ---------------------------------------------------------
# Daily Report — PDF
# ---------------------------------------------------------
@router.get("/pdf", dependencies=[Depends(get_current_user)])
def daily_report_pdf(date: str = None):
    target_date = datetime.date.today() if not date else datetime.datetime.strptime(date, "%Y-%m-%d").date()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        data = _gather_daily_report_data(cursor, target_date)
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    try:
        pdf_bytes = generate_daily_report(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation error: {e}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="daily_report_{data["date"]}.pdf"'},
    )


# ---------------------------------------------------------
# Daily Report — WhatsApp-ready text summary
# ---------------------------------------------------------
@router.get("/summary-text", dependencies=[Depends(get_current_user)])
def daily_report_summary_text(date: str = None):
    target_date = datetime.date.today() if not date else datetime.datetime.strptime(date, "%Y-%m-%d").date()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        data = _gather_daily_report_data(cursor, target_date)
        whatsapp_number = get_text_setting(cursor, "client_whatsapp_number", "")
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    lines = [f"*Daily Report — {data['date']}*", ""]

    lines.append("*Production:*")
    if data["production"]:
        p = data["production"]
        lines.append(f"Mixes: {p['mixes']} | Bricks: {p['bricks_produced']}")
        average = p["avg_bricks_per_mix"]
        qualifier = " (estimated)" if p["average_is_estimated"] else ""
        lines.append(f"Average bricks per mix{qualifier}: {average if average is not None else 'N/A'}")
        lines.append(f"Labourers: {p['labourers']}")
    else:
        lines.append("No production entry logged today.")
    lines.append("")

    lines.append("*Raw Material Stock:*")
    for material, info in data["stock"].items():
        lines.append(f"{material}: {info['qty']} {info['unit']}")
    lines.append("")

    finished = data["finished_bricks"]
    lines.append("*Finished Brick Availability:*")
    lines.append(f"Total: {finished['total_bricks']} | Saleable now: {finished['saleable']}")
    lines.append(f"Under 7 days: {finished['curing']} | Early-sale eligible (7-13 days): {finished['early_sale']} | Fully cured (14+ days): {finished['fully_cured']}")
    lines.append("")

    lines.append("*Sales Today:*")
    s = data["sales"]
    if s["count"] > 0:
        lines.append(f"{s['count']} sale(s), {s['total_bricks']} bricks, Rs. {s['total_revenue']:.2f} billed, Rs. {s['total_paid']:.2f} collected")
    else:
        lines.append("No sales recorded today.")

    return {"text": "\n".join(lines), "whatsapp_number": whatsapp_number, "date": data["date"]}
