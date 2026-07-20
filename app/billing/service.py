"""Billing logic: start a subscription, verify it, and react to webhooks.

State lives entirely in the existing ``profiles.plan`` column — no new tables.
The webhook (signature-verified) is the source of truth; verify() also flips
the plan so the user sees the upgrade immediately on return.
"""

from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import HTTPException, status

from app.auth.repository import AuthRepository
from app.auth.schemas import Plan
from app.billing.client import PaystackClient, PaystackError
from app.billing.schemas import CheckoutResponse, VerifyResponse
from app.core import discord
from app.core.config import settings


def _major_amount(data: dict) -> float | None:
    """Paystack amounts are in the minor unit (kobo/cents) — convert to major."""
    amount = data.get("amount")
    return amount / 100 if isinstance(amount, (int, float)) else None

# Events that mean "this plan is now active".
_ACTIVATE_EVENTS = {"charge.success", "subscription.create"}
# Events that mean "the subscription ended" -> fall back to the base tier.
_DEACTIVATE_EVENTS = {"subscription.disable", "subscription.not_renew"}


class BillingService:
    def __init__(self, auth_repo: AuthRepository, client: PaystackClient) -> None:
        self.auth_repo = auth_repo
        self.client = client

    # --- plan <-> Paystack plan code -------------------------------------
    def _plan_code(self, plan: Plan) -> str:
        return {
            Plan.starter: settings.paystack_plan_starter,
            Plan.beta: settings.paystack_plan_beta,
            Plan.pro: settings.paystack_plan_pro,
        }[plan]

    def _plan_amount(self, plan: Plan) -> int:
        return {
            Plan.starter: settings.paystack_amount_starter,
            Plan.beta: settings.paystack_amount_beta,
            Plan.pro: settings.paystack_amount_pro,
        }[plan]

    def _plan_from_code(self, code: str | None) -> Plan | None:
        if not code:
            return None
        return {
            settings.paystack_plan_starter: Plan.starter,
            settings.paystack_plan_beta: Plan.beta,
            settings.paystack_plan_pro: Plan.pro,
        }.get(code)

    def _resolve_plan(self, data: dict) -> Plan | None:
        """Work out which plan a Paystack payload refers to."""
        plan_obj = data.get("plan")
        if isinstance(plan_obj, dict):
            resolved = self._plan_from_code(plan_obj.get("plan_code"))
            if resolved:
                return resolved
        meta = data.get("metadata") or {}
        value = meta.get("plan")
        if value:
            try:
                return Plan(value)
            except ValueError:
                return None
        return None

    # --- flows ------------------------------------------------------------
    def checkout(
        self, user_id: str, email: str, plan: Plan
    ) -> CheckoutResponse:
        try:
            data = self.client.initialize(
                email=email,
                plan_code=self._plan_code(plan),
                amount=self._plan_amount(plan),
                currency=settings.paystack_currency,
                callback_url=f"{settings.frontend_url}/billing/callback",
                metadata={"user_id": user_id, "plan": plan.value},
            )
        except PaystackError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            )
        return CheckoutResponse(
            authorization_url=data["authorization_url"],
            reference=data["reference"],
        )

    def verify(self, reference: str, user_id: str) -> VerifyResponse:
        try:
            data = self.client.verify(reference)
        except PaystackError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            )
        if data.get("status") != "success":
            return VerifyResponse(status=data.get("status", "failed"), plan=None)

        plan = self._resolve_plan(data)
        if plan:
            self.auth_repo.set_plan(user_id, plan.value)
            discord.notify_payment(
                (data.get("customer") or {}).get("email") or "",
                plan.value,
                amount=_major_amount(data),
                currency=data.get("currency"),
                source="checkout",
            )
        return VerifyResponse(status="success", plan=plan)

    def handle_webhook(self, raw_body: bytes, signature: str) -> None:
        secret = settings.paystack_secret_key
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Billing not configured",
            )
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha512).hexdigest()
        if not hmac.compare_digest(expected, signature or ""):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )

        payload = json.loads(raw_body.decode() or "{}")
        event = payload.get("event", "")
        data = payload.get("data", {})
        email = (data.get("customer") or {}).get("email")
        if not email:
            return

        if event in _ACTIVATE_EVENTS:
            plan = self._resolve_plan(data)
            if plan:
                self.auth_repo.set_plan_by_email(email, plan.value)
                discord.notify_payment(
                    email,
                    plan.value,
                    amount=_major_amount(data),
                    currency=data.get("currency"),
                    source="webhook",
                )
        elif event in _DEACTIVATE_EVENTS:
            # Subscription ended -> drop to the base tier.
            self.auth_repo.set_plan_by_email(email, Plan.starter.value)
