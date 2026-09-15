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
from cost_history import labour_cost_for_hours
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

    from routers.dashboard import activity_for_date
    daily=activity_for_date(target_date)
    production=daily['production']
    if production:production['average_is_estimated']=False
    sales=daily['sales']

    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "production": production,
        "stock": stock_display,
        "stock_as_of": str(__import__("batch_stock").factory_today()),
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

    lines = [f"*Daily Report — {target_date.strftime('%d-%m-%Y')}*", ""]

    lines.append("*Production:*")
    if data["production"]:
        p = data["production"]
        lines.append(f"Mixes: {p['mixes']} | Bricks: {p['bricks_produced']}")
        average = p["avg_bricks_per_mix"]
        qualifier = " (estimated)" if p["average_is_estimated"] else ""
        lines.append(f"Average bricks per mix{qualifier}: {average if average is not None else 'N/A'}")
        lines.append(f"Working hours: {p['labour_hours'] if p['labour_hours'] is not None else 'Not recorded'}; cost: Rs. {p['labour_cost'] if p['labour_cost'] is not None else 'Hours needed'}")
        lines.append(f"Labour cost per brick: Rs. {p['labour_cost_per_brick'] if p['labour_cost_per_brick'] is not None else 'N/A'}")
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

    lines.append("*Sales:*")
    s = data["sales"]
    if s["count"] > 0:
        lines.append(f"{s['count']} sale(s), {s['total_bricks']} bricks, Rs. {s['total_revenue'] if s['total_revenue'] is not None else 'Not recorded'} billed, Rs. {s['total_paid'] if s['total_paid'] is not None else 'Not recorded'} collected")
    else:
        lines.append("No sales recorded today.")

    return {"text": "\n".join(lines), "whatsapp_number": whatsapp_number, "date": data["date"]}
