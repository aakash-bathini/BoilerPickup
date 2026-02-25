"""Email service for verification codes. Uses SMTP when configured."""
import os
import smtplib
import random
import string
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Ensure .env is loaded (in case module imported before main's load_dotenv)
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass


def generate_code() -> str:
    return "".join(random.choices(string.digits, k=6))


def send_verification_email(to_email: str, code: str) -> tuple[bool, str]:
    """Send verification code to email. Returns (success, error_message)."""
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    from_addr = os.getenv("SMTP_FROM", "").strip() or user

    subject = "Your Boiler Pickup Verification Code"
    body = f"""Hello!

Your verification code for Boiler Pickup is: {code}

Enter this code on the verification page to complete your registration.

This code expires in 15 minutes.

— Boiler Pickup Team
"""

    if not host or not user or not password:
        print(f"[DEV] SMTP not configured. Verification code for {to_email}: {code}")
        return False, "SMTP not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in backend/.env"

    try:
        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        # Remove spaces from app password (Google shows "xxxx xxxx xxxx xxxx")
        password_clean = password.replace(" ", "")

        # Try SSL (port 465) first — often more reliable than STARTTLS (587)
        if port == 465:
            with smtplib.SMTP_SSL(host, port) as server:
                server.login(user, password_clean)
                server.sendmail(from_addr, to_email, msg.as_string())
        else:
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(user, password_clean)
                server.sendmail(from_addr, to_email, msg.as_string())
        return True, ""
    except Exception as e:
        err = str(e)
        print(f"Email send failed: {err}")
        return False, err
