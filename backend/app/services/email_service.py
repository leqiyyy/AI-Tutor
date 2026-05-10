from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


def send_email(*, to_email: str, subject: str, text: str, html: str | None = None) -> None:
    """Send a single transactional email through the configured SMTP server."""
    if settings.EMAIL_DEV_MODE:
        log.info("email_dev_mode", to_email=to_email, subject=subject, text=text)
        return

    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        raise RuntimeError("SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = _format_sender()
    message["To"] = to_email
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")

    if settings.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)
        return

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls()
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(message)


def send_verify_code_email(*, to_email: str, code: str, purpose: str, expires_minutes: int) -> None:
    purpose_label = "重置密码" if purpose == "reset_password" else "注册账号"
    subject = f"珞樱学堂{purpose_label}验证码"
    text = (
        f"您正在进行珞樱学堂{purpose_label}操作。\n\n"
        f"验证码：{code}\n"
        f"有效期：{expires_minutes} 分钟\n\n"
        "如果不是您本人操作，请忽略本邮件。"
    )
    html = (
        "<div style=\"font-family:Arial,'Microsoft YaHei',sans-serif;line-height:1.7;color:#1f2937;\">"
        f"<p>您正在进行珞樱学堂{purpose_label}操作。</p>"
        f"<p style=\"font-size:24px;font-weight:700;letter-spacing:4px;\">{code}</p>"
        f"<p>验证码有效期为 {expires_minutes} 分钟。</p>"
        "<p style=\"color:#6b7280;\">如果不是您本人操作，请忽略本邮件。</p>"
        "</div>"
    )
    send_email(to_email=to_email, subject=subject, text=text, html=html)


def _format_sender() -> str:
    sender = settings.EMAIL_FROM.strip() or settings.SMTP_USER
    if "<" in sender and ">" in sender:
        return sender
    return formataddr(("珞樱学堂", sender))
