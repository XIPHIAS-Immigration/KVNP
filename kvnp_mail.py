"""Outbound email for PassportLens over plain SMTP (works with AWS SES SMTP
credentials, Google Workspace, or any provider). Nothing is sent when SMTP is
not configured; callers still get a sensible return value so the product keeps
working without email during local development."""

from __future__ import annotations

import html
import os
import smtplib
import sys
import threading
from email.message import EmailMessage
from email.utils import formataddr

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or 587)
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip()
SMTP_SECURE = os.getenv("SMTP_SECURE", "starttls").strip().lower()  # starttls | ssl | none
MAIL_FROM = os.getenv("MAIL_FROM", "").strip() or SMTP_USER
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "PassportLens").strip()
CONTACT_TO = [item.strip() for item in os.getenv("KVNP_CONTACT_EMAIL", "").split(",") if item.strip()]
PRODUCT_NAME = "PassportLens"


def configured() -> bool:
    return bool(SMTP_HOST and MAIL_FROM)


def _log(message: str) -> None:
    print(f"[kvnp-mail] {message}", file=sys.stderr, flush=True)


def _send(message: EmailMessage) -> bool:
    try:
        if SMTP_SECURE == "ssl":
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
        with server:
            server.ehlo()
            if SMTP_SECURE == "starttls":
                server.starttls()
                server.ehlo()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASS)
            server.send_message(message)
        return True
    except Exception as error:  # never let email break a request
        _log(f"send failed: {type(error).__name__}: {str(error)[:200]}")
        return False


def send(to: list[str] | str, subject: str, text: str, html_body: str | None = None, reply_to: str | None = None, background: bool = True) -> bool:
    recipients = [to] if isinstance(to, str) else list(to)
    recipients = [item for item in recipients if item and "@" in item]
    if not recipients:
        return False
    if not configured():
        _log(f"SMTP not configured; would send '{subject}' to {', '.join(recipients)}")
        return False
    message = EmailMessage()
    message["From"] = formataddr((MAIL_FROM_NAME, MAIL_FROM))
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(text)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    if background:
        threading.Thread(target=_send, args=(message,), daemon=True).start()
        return True
    return _send(message)


def _wrap(title: str, body_html: str, footer: str = "") -> str:
    return f"""<!doctype html><html><body style="margin:0;background:#f5f7fa;font-family:Segoe UI,Arial,sans-serif;color:#0f1f33">
<div style="max-width:560px;margin:24px auto;background:#fff;border:1px solid #e3e8ef;border-radius:14px;overflow:hidden">
<div style="background:#351C15;padding:18px 24px;color:#fff;font-weight:800;font-size:18px">Passport<span style="color:#FFB500">Lens</span></div>
<div style="padding:24px"><h2 style="margin:0 0 12px;color:#351C15;font-size:20px">{html.escape(title)}</h2>{body_html}</div>
<div style="padding:14px 24px;border-top:1px solid #e3e8ef;color:#6f7e92;font-size:12px">{footer or 'PassportLens · KVNP Holdings Inc'}</div>
</div></body></html>"""


def send_enquiry_notification(enquiry: dict, reference: str) -> bool:
    if not CONTACT_TO:
        _log("KVNP_CONTACT_EMAIL not set; enquiry saved in admin only")
        return False
    tier = enquiry.get("tier") or "Question"
    subject = f"[{PRODUCT_NAME}] {tier} enquiry from {enquiry.get('business') or enquiry.get('name')} ({reference})"
    lines = [
        f"Reference: {reference}",
        f"Name: {enquiry.get('name')}",
        f"Business: {enquiry.get('business') or '-'}",
        f"Email: {enquiry.get('email')}",
        f"Phone: {enquiry.get('phone') or '-'}",
        f"Interested in: {tier}",
        "",
        enquiry.get("message") or "",
    ]
    rows = "".join(
        f"<tr><td style='padding:6px 10px 6px 0;color:#6f7e92'>{html.escape(k)}</td><td style='padding:6px 0'>{html.escape(str(v or '-'))}</td></tr>"
        for k, v in (
            ("Reference", reference),
            ("Name", enquiry.get("name")),
            ("Business", enquiry.get("business")),
            ("Email", enquiry.get("email")),
            ("Phone", enquiry.get("phone")),
            ("Interested in", tier),
        )
    )
    body = f"<table style='font-size:14px;border-collapse:collapse'>{rows}</table><p style='white-space:pre-wrap;font-size:14px;margin-top:16px'>{html.escape(enquiry.get('message') or '')}</p>"
    return send(CONTACT_TO, subject, "\n".join(lines), _wrap("New enquiry", body), reply_to=enquiry.get("email"))


def send_enquiry_receipt(email: str, name: str, reference: str) -> bool:
    text = (
        f"Hi {name},\n\nThanks for contacting PassportLens. Your reference is {reference}. "
        "We reply by email within one business day.\n\nPassportLens team"
    )
    body = f"<p>Hi {html.escape(name)},</p><p>Thanks for contacting PassportLens. Your reference is <b>{html.escape(reference)}</b>. We reply by email within one business day.</p>"
    return send(email, f"We received your message ({reference})", text, _wrap("Thanks — we'll be in touch", body))


def send_invite(email: str, org_name: str, invite_url: str, inviter: str | None = None) -> bool:
    who = f"{inviter} has" if inviter else "You have been"
    text = (
        f"{who} invited you to join {org_name} on PassportLens.\n\n"
        f"Open this link to set your password and sign in (valid for 7 days):\n{invite_url}\n\n"
        "If you were not expecting this, you can ignore this email."
    )
    body = (
        f"<p>{html.escape(who)} invited you to join <b>{html.escape(org_name)}</b> on PassportLens.</p>"
        f"<p><a href='{html.escape(invite_url)}' style='display:inline-block;background:#FFB500;color:#351C15;font-weight:800;padding:12px 20px;border-radius:999px;text-decoration:none'>Accept invitation</a></p>"
        f"<p style='font-size:13px;color:#6f7e92'>The link is valid for 7 days. If the button does not work, copy this address:<br>{html.escape(invite_url)}</p>"
    )
    return send(email, f"You're invited to {org_name} on PassportLens", text, _wrap("You're invited", body))


def send_welcome(email: str, name: str, plan_label: str, login_url: str) -> bool:
    text = f"Hi {name},\n\nYour PassportLens {plan_label} is active. Sign in at {login_url}\n\nPassportLens team"
    body = f"<p>Hi {html.escape(name)},</p><p>Your PassportLens <b>{html.escape(plan_label)}</b> is active.</p><p><a href='{html.escape(login_url)}'>Open the studio</a></p>"
    return send(email, f"Welcome to PassportLens — {plan_label} active", text, _wrap("Welcome to PassportLens", body))
