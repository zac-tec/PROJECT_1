"""
SCHEDULER
Runs a background job once a day at whatever time is set in Delivery
Settings, and emails the daily report if auto-send is turned on.

IMPORTANT: this only fires while the server is actually running. If
uvicorn isn't running at 8:00 PM, that day's email simply doesn't send —
there's no way around this, it's just what "run a task at a specific
time" requires. Fine for now while testing locally; matters once this
moves to a server that stays on.

Uses APScheduler's BackgroundScheduler (thread-based) since the rest of
this app is synchronous (plain psycopg2), so the scheduled job can just
be normal, boring, synchronous Python — no async complexity needed.
"""

import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from database import get_connection
from services import get_text_setting
from pdf_generator import generate_daily_report
from email_sender import send_daily_report_email

JOB_ID = "daily_report_email"
scheduler = BackgroundScheduler()


def _run_scheduled_report():
    """The actual job body — checks if auto-send is on, and if so, builds and emails today's report."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        enabled = get_text_setting(cursor, "daily_send_enabled", "false")
        if enabled != "true":
            cursor.close()
            conn.close()
            return  # auto-send is off — do nothing, silently

        recipient = get_text_setting(cursor, "client_email", "")

        # Reuse the same data-gathering logic as the on-demand PDF endpoint.
        from routers.daily_report import _gather_daily_report_data
        target_date = datetime.date.today()
        data = _gather_daily_report_data(cursor, target_date)
        cursor.close()
    except Exception as e:
        print(f"[scheduler] Failed to gather daily report data: {e}")
        conn.close()
        return
    finally:
        if not conn.closed:
            conn.close()

    try:
        pdf_bytes = generate_daily_report(data)
        send_daily_report_email(recipient, pdf_bytes, data["date"], data["production"])
        print(f"[scheduler] Daily report emailed successfully to {recipient} for {data['date']}.")
    except Exception as e:
        # Deliberately just logged, not raised — a scheduled background
        # job has no one to show an error to, so print is the right move.
        print(f"[scheduler] Failed to send daily report email: {e}")


def _parse_time(time_str: str):
    try:
        hour, minute = map(int, time_str.strip().split(":"))
        return hour, minute
    except Exception:
        return 20, 0  # fallback: 8:00 PM


def start_scheduler():
    """Call once at app startup — reads the current schedule time from the DB and starts the job."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        time_str = get_text_setting(cursor, "daily_send_time", "20:00")
        cursor.close()
    finally:
        conn.close()

    hour, minute = _parse_time(time_str)
    scheduler.add_job(_run_scheduled_report, CronTrigger(hour=hour, minute=minute), id=JOB_ID, replace_existing=True)
    scheduler.start()
    print(f"[scheduler] Daily report job scheduled for {hour:02d}:{minute:02d} every day.")


def reschedule(time_str: str):
    """Called from the Delivery Settings endpoint whenever the admin changes the send time."""
    hour, minute = _parse_time(time_str)
    scheduler.reschedule_job(JOB_ID, trigger=CronTrigger(hour=hour, minute=minute))
    print(f"[scheduler] Daily report job rescheduled to {hour:02d}:{minute:02d}.")
