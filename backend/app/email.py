import resend
import os
from datetime import datetime, timezone, timedelta
import secrets

resend.api_key = os.environ["RESEND_API_KEY"]
FRONTEND_URL = os.environ["FRONTEND_URL"]

def generate_verification_token():
    return secrets.token_urlsafe(32)

def verification_token_expiry():
    return datetime.now(timezone.utc) + timedelta(hours=24)

async def send_verification_email(email: str, username: str, token: str):
    verification_url = f"{FRONTEND_URL}/verify-email?token={token}"
    resend.Emails.send({
        "from": "noreply@pkhleb.com",
        "to": email,
        "subject": "Verify your journal account",
        "html": f"""
            <p>Hi {username},</p>
            <p>Click the link below to verify your email address:</p>
            <p><a href="{verification_url}">{verification_url}</a></p>
            <p>This link expires in 24 hours.</p>
            <p>If you didn't create an account, you can ignore this email.</p>
        """
    })
