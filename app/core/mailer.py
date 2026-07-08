"""Transactional email via ZeptoMail (Zoho).

Sends verification, password-reset, and agent-created emails through the
ZeptoMail API. No new dependency — uses httpx. If ZEPTO_TOKEN isn't set, sends
are skipped with a warning so local/dev flows don't crash.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("ensight.mailer")

_BRAND = "#2563eb"


class MailError(Exception):
    """Raised when an email fails to send."""


def _auth_header() -> str:
    token = settings.zepto_token
    # ZeptoMail expects "Zoho-enczapikey <token>"; accept either form.
    return token if token.lower().startswith("zoho-") else f"Zoho-enczapikey {token}"


def _send(*, to_email: str, subject: str, html: str) -> None:
    if not settings.zepto_token:
        logger.warning("ZEPTO_TOKEN not set — skipping email to %s", to_email)
        return
    payload = {
        "from": {
            "address": settings.mail_from_email,
            "name": settings.mail_from_name,
        },
        "to": [{"email_address": {"address": to_email}}],
        "subject": subject,
        "htmlbody": html,
    }
    try:
        with httpx.Client(timeout=20) as client:
            res = client.post(
                settings.zepto_api_url,
                json=payload,
                headers={
                    "Authorization": _auth_header(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
    except httpx.HTTPError as exc:
        raise MailError(f"Couldn't reach ZeptoMail: {exc}") from exc
    if res.status_code >= 400:
        raise MailError(f"ZeptoMail error {res.status_code}: {res.text[:300]}")


_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def _button(text: str, url: str) -> str:
    """A 'bulletproof' button: table cell + bgcolor renders in Outlook too."""
    if not text:
        return ""
    return f"""\
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:26px 0 8px;">
        <tr>
          <td align="center" bgcolor="{_BRAND}" style="border-radius:8px;">
            <a href="{url}" target="_blank"
               style="display:inline-block;padding:14px 30px;font-family:{_FONT};font-size:15px;
                      font-weight:600;line-height:1;color:#ffffff;text-decoration:none;border-radius:8px;">
              {text}
            </a>
          </td>
        </tr>
      </table>"""


def _fallback_link(url: str) -> str:
    if not url:
        return ""
    return f"""\
      <p style="margin:16px 0 0;font-size:13px;line-height:1.6;color:#94a3b8;font-family:{_FONT};">
        Or paste this link into your browser:<br>
        <a href="{url}" target="_blank" style="color:{_BRAND};word-break:break-all;">{url}</a>
      </p>"""


def _layout(
    *,
    heading: str,
    body: str,
    button_text: str = "",
    button_url: str = "",
    preheader: str = "",
) -> str:
    year = "2026"
    return f"""\
<!doctype html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="x-apple-disable-message-reformatting">
  <title>EnsightLabs</title>
</head>
<body style="margin:0;padding:0;background-color:#eef2f9;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;font-size:1px;line-height:1px;color:#eef2f9;">
    {preheader}&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;
  </div>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#eef2f9;">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
               style="width:600px;max-width:600px;background-color:#ffffff;border-radius:16px;overflow:hidden;
                      box-shadow:0 1px 3px rgba(15,23,42,0.08);">

          <!-- Header -->
          <tr>
            <td bgcolor="{_BRAND}"
                style="background-color:{_BRAND};background-image:linear-gradient(135deg,#1e40af,{_BRAND} 55%,#38bdf8);
                       padding:26px 32px;">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="padding-right:12px;">
                    <div style="width:40px;height:40px;background-color:rgba(255,255,255,0.18);border-radius:11px;
                                text-align:center;line-height:40px;font-family:{_FONT};font-size:22px;
                                font-weight:700;color:#ffffff;">E</div>
                  </td>
                  <td style="font-family:{_FONT};font-size:20px;font-weight:700;color:#ffffff;letter-spacing:-0.2px;">
                    EnsightLabs
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 32px 8px;">
              <h1 style="margin:0 0 14px;font-family:{_FONT};font-size:22px;line-height:1.3;font-weight:700;color:#0f172a;">
                {heading}
              </h1>
              <div style="font-family:{_FONT};font-size:15px;line-height:1.65;color:#475569;">
                {body}
              </div>
              {_button(button_text, button_url)}
              {_fallback_link(button_url)}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:28px 32px 32px;">
              <div style="border-top:1px solid #e2e8f0;padding-top:20px;">
                <p style="margin:0 0 6px;font-family:{_FONT};font-size:13px;color:#64748b;">
                  <strong style="color:#334155;">EnsightLabs</strong> — AI that answers, converts &amp; grows your business.
                </p>
                <p style="margin:0;font-family:{_FONT};font-size:12px;color:#94a3b8;">
                  Need help? Email
                  <a href="mailto:hello@ensightlabs.xyz" style="color:{_BRAND};text-decoration:none;">hello@ensightlabs.xyz</a>
                  &nbsp;·&nbsp;
                  <a href="{settings.frontend_url}" style="color:{_BRAND};text-decoration:none;">ensightlabs.xyz</a>
                </p>
                <p style="margin:12px 0 0;font-family:{_FONT};font-size:11px;color:#cbd5e1;">
                  © {year} EnsightLabs. You received this email because an account was created with this address.
                </p>
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# --- public senders --------------------------------------------------------


def send_verification_email(to_email: str, token: str) -> None:
    link = f"{settings.frontend_url}/verify-email?token={token}"
    html = _layout(
        preheader="Confirm your email to activate your EnsightLabs account.",
        heading="Welcome — confirm your email",
        body=(
            "Thanks for signing up for EnsightLabs. Tap the button below to "
            "confirm your email address and activate your account.<br><br>"
            "<span style=\"color:#94a3b8;font-size:13px;\">This link expires in "
            "24 hours. If you didn't create an account, you can ignore this "
            "email.</span>"
        ),
        button_text="Confirm my email",
        button_url=link,
    )
    _send(to_email=to_email, subject="Confirm your EnsightLabs email", html=html)


def send_password_reset_email(to_email: str, token: str) -> None:
    link = f"{settings.frontend_url}/reset-password?token={token}"
    html = _layout(
        preheader="Reset your EnsightLabs password.",
        heading="Reset your password",
        body=(
            "We received a request to reset your EnsightLabs password. Tap the "
            "button below to choose a new one.<br><br>"
            "<span style=\"color:#94a3b8;font-size:13px;\">This link expires in "
            "24 hours. If you didn't request this, you can safely ignore this "
            "email — your password won't change.</span>"
        ),
        button_text="Reset my password",
        button_url=link,
    )
    _send(to_email=to_email, subject="Reset your EnsightLabs password", html=html)


def send_agent_created_email(to_email: str, agent_name: str) -> None:
    html = _layout(
        preheader=f"Your agent “{agent_name}” is ready to train and embed.",
        heading="Your AI agent is ready 🎉",
        body=(
            f"Your agent <strong>{agent_name}</strong> has been created. "
            "Here's what to do next:<br><br>"
            "<strong>1.</strong> Upload documents to train it on your business.<br>"
            "<strong>2.</strong> Turn on booking (optional) to let it schedule meetings.<br>"
            "<strong>3.</strong> Copy the embed code and add it to your website.<br>"
        ),
        button_text="Open dashboard",
        button_url=f"{settings.frontend_url}/dashboard/agents",
    )
    _send(
        to_email=to_email,
        subject=f"Your agent “{agent_name}” is ready",
        html=html,
    )
