"""
Email service using Resend REST API for transactional emails.
"""

import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

RESEND_API_URL = "https://api.resend.com/emails"


class EmailService:
    """Sends transactional emails via the Resend API."""

    def __init__(self) -> None:
        self.api_key = settings.resend_api_key
        self.from_email = settings.resend_from_email

    async def send_password_reset_code(
        self,
        to_email: str,
        code: str,
        user_name: Optional[str] = None,
    ) -> bool:
        """
        Send a password reset code email.

        Returns True if the email was sent successfully, False otherwise.
        """
        display_name = user_name or "there"
        subject = f"{code} is your KnowIt password reset code"

        html_body = _build_reset_email_html(code, display_name)
        text_body = _build_reset_email_text(code, display_name)

        return await self._send_email(
            to=to_email,
            subject=subject,
            html=html_body,
            text=text_body,
        )

    async def _send_email(
        self,
        to: str,
        subject: str,
        html: str,
        text: str,
    ) -> bool:
        """Send an email via Resend API. Returns True on success."""
        if not self.api_key:
            logger.error("[EmailService] Resend API key not configured")
            return False

        payload = {
            "from": f"KnowIt <{self.from_email}>",
            "to": [to],
            "subject": subject,
            "html": html,
            "text": text,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    RESEND_API_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )

            if response.status_code == 200:
                logger.info(f"[EmailService] Password reset email sent to {to}")
                return True

            logger.error(
                f"[EmailService] Resend API error: {response.status_code} - {response.text}"
            )
            return False

        except httpx.TimeoutException:
            logger.error(f"[EmailService] Timeout sending email to {to}")
            return False
        except httpx.HTTPError as e:
            logger.error(f"[EmailService] HTTP error sending email to {to}: {e}")
            return False


def _build_reset_email_html(code: str, display_name: str) -> str:
    """Build branded HTML email for password reset code."""
    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
             max-width: 480px; margin: 0 auto; padding: 40px 20px; color: #1a1a1a;">
  <h2 style="margin-bottom: 8px;">Reset your password</h2>
  <p>Hi {display_name},</p>
  <p>Use the code below to reset your KnowIt password. It expires in 15 minutes.</p>
  <div style="background: #f4f4f5; border-radius: 8px; padding: 24px;
              text-align: center; margin: 24px 0;">
    <span style="font-size: 32px; font-weight: 700; letter-spacing: 6px;
                 font-family: monospace;">{code}</span>
  </div>
  <p style="color: #71717a; font-size: 14px;">
    If you didn't request this, you can safely ignore this email.
  </p>
  <hr style="border: none; border-top: 1px solid #e4e4e7; margin: 32px 0;">
  <p style="color: #a1a1aa; font-size: 12px;">KnowIt &mdash; Learn smarter</p>
</body>
</html>"""


def _build_reset_email_text(code: str, display_name: str) -> str:
    """Build plain text fallback for password reset code."""
    return (
        f"Hi {display_name},\n\n"
        f"Your KnowIt password reset code is: {code}\n\n"
        "This code expires in 15 minutes.\n\n"
        "If you didn't request this, you can safely ignore this email.\n"
    )
