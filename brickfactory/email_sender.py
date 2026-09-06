"""
EMAIL SENDER (via Resend)
Sends the daily report PDF to the configured client email. Resend's free
tier covers 100 emails/day, no App Password dance needed — just an API key.

RESEND_FROM_EMAIL defaults to onboarding@resend.dev for testing (Resend's
own shared sending address, works immediately with no setup). Once you
verify your own domain on resend.com, switch it to your own address in
.env for a more professional "From" — same code, just a config change.
"""

import os
import base64
import resend
from dotenv import load_dotenv

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")


def send_daily_report_email(recipient_email: str, pdf_bytes: bytes, report_date: str, production: dict | None = None):
    """
    Raises an exception on failure — caller decides how to handle/log it
    (the scheduled job catches and logs; the on-demand endpoint surfaces
    it to the user directly).
    """
    if not resend.api_key:
        raise RuntimeError("RESEND_API_KEY is not set in .env — email sending is not configured yet.")
    if not recipient_email:
        raise RuntimeError("No client email address is set. Add one in Delivery Settings first.")

    average_html = ""
    if production:
        average = production["avg_bricks_per_mix"]
        qualifier = " (estimated)" if production["average_is_estimated"] else ""
        average_html = f"<p>Average bricks per mix{qualifier}: <strong>{average if average is not None else 'N/A'}</strong></p>"

    attachment = {
        "filename": f"daily_report_{report_date}.pdf",
        "content": base64.b64encode(pdf_bytes).decode("utf-8"),
    }

    resend.Emails.send({
        "from": RESEND_FROM_EMAIL,
        "to": [recipient_email],
        "subject": f"Daily Report - {report_date}",
        "html": (
            f"<p>Please find attached today's stock, production, and sales report "
            f"for <strong>{report_date}</strong>.</p>"
            f"{average_html}"
            f"<p style='color:#888;font-size:12px;'>Sent automatically by the Brick Factory Management System.</p>"
        ),
        "attachments": [attachment],
    })
