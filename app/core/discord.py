"""Discord alerts via an incoming webhook.

Fire-and-forget notifications for the events a founder wants to see live:
new signups, successful payments, and unhandled backend errors. Uses httpx
(already a dependency) and posts from a daemon thread so it never blocks the
request path. If ``DISCORD_WEBHOOK_URL`` isn't set, every call is a silent
no-op, so it's safe to leave the hooks in place in any environment.
"""

from __future__ import annotations

import logging
import threading
import traceback

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Discord embed accent colors (decimal RGB).
_GREEN = 0x2ECC71
_BLURPLE = 0x5865F2
_RED = 0xED4245

# Discord caps an embed field "value" at 1024 chars.
_FIELD_MAX = 1024


def _post(embed: dict) -> None:
    """Send one embed to the webhook. Best-effort — never raises."""
    url = settings.discord_webhook_url
    if not url:
        return
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json={"embeds": [embed]})
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Discord alert failed: %s", exc)


def _dispatch(embed: dict) -> None:
    """Fire the post in a background thread so callers never block or fail."""
    if not settings.discord_webhook_url:
        return
    threading.Thread(target=_post, args=(embed,), daemon=True).start()


def notify_signup(email: str) -> None:
    """A new user signed up."""
    _dispatch(
        {
            "title": "🎉 New signup",
            "color": _GREEN,
            "fields": [
                {"name": "Email", "value": email or "—", "inline": True},
            ],
        }
    )


def notify_payment(
    email: str,
    plan: str | None,
    *,
    amount: float | None = None,
    currency: str | None = None,
    source: str = "webhook",
) -> None:
    """A successful payment / plan activation.

    ``source`` distinguishes the checkout-redirect verification from the
    Paystack webhook, so duplicate alerts (if both fire) are easy to tell apart.
    """
    fields = [{"name": "Email", "value": email or "—", "inline": True}]
    if plan:
        fields.append({"name": "Plan", "value": plan, "inline": True})
    if amount is not None:
        money = f"{amount:,.2f} {currency or ''}".strip()
        fields.append({"name": "Amount", "value": money, "inline": True})
    fields.append({"name": "Source", "value": source, "inline": True})
    _dispatch(
        {"title": "💰 Payment received", "color": _BLURPLE, "fields": fields}
    )


def notify_error(where: str, exc: BaseException) -> None:
    """An unhandled backend error. ``where`` is e.g. ``"POST /chat"``."""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    # Keep the tail — the deepest frames are the useful ones — and leave room
    # for the code-fence characters within the 1024-char field cap.
    tb = tb[-(_FIELD_MAX - 12):]
    _dispatch(
        {
            "title": "🚨 Backend error",
            "color": _RED,
            "fields": [
                {"name": "Where", "value": (where or "—")[:_FIELD_MAX]},
                {
                    "name": "Error",
                    "value": f"{type(exc).__name__}: {exc}"[:_FIELD_MAX],
                },
                {"name": "Traceback", "value": f"```\n{tb}\n```"},
            ],
        }
    )
