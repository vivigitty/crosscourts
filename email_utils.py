# =========================================================
# email_utils.py
# Gmail SMTP email sending for password reset
# =========================================================

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import streamlit as st
from constants import SMTP_FROM_NAME


# =========================================================
# ✅ Load SMTP credentials (.env locally / secrets.toml in Cloud)
# =========================================================

def get_smtp_credentials():
    try:
        email = st.secrets["SMTP_EMAIL"]
        password = st.secrets["SMTP_PASSWORD"]
        host = st.secrets.get("SMTP_HOST", "smtp.gmail.com")
        port = int(st.secrets.get("SMTP_PORT", 587))
        return email, password, host, port
    except Exception:
        # LOCAL fallback
        import os
        from dotenv import load_dotenv
        load_dotenv()

        email = os.getenv("SMTP_EMAIL")
        password = os.getenv("SMTP_PASSWORD")
        host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        port = int(os.getenv("SMTP_PORT", "587"))

        if not email or not password:
            raise ValueError("❌ Missing SMTP_EMAIL or SMTP_PASSWORD in .env or Streamlit secrets.")

        return email, password, host, port


# =========================================================
# ✅ Send Password Reset Email
# =========================================================

def send_reset_email(to_email: str, token: str):
    """Send a Gmail SMTP password reset email."""
    sender_email, sender_password, smtp_host, smtp_port = get_smtp_credentials()

    reset_link = f"{st.secrets.get('APP_URL', 'http://localhost:8501')}?reset_token={token}"

    html_body = f"""
    <html>
        <body>
            <h2>Cross Courts – Password Reset</h2>
            <p>Hello,</p>
            <p>You requested to reset your Cross Courts account password.</p>

            <p><b>Click below to reset:</b></p>
            <p><a href="{reset_link}">{reset_link}</a></p>

            <p>If you did NOT request this, you can ignore this email.</p>

            <br>
            <p>Thanks,<br>Cross Courts Admin</p>
        </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Cross Courts – Password Reset"
    msg["From"] = formataddr((SMTP_FROM_NAME, sender_email))
    msg["To"] = to_email

    msg.attach(MIMEText(html_body, "html"))

    try:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()

        print(f"[EMAIL SENT] Reset link sent to {to_email}")
        return True

    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        raise e
