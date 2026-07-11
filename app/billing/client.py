"""Thin Paystack HTTP client (httpx). No new dependencies, no DB state."""

import httpx

from app.core.config import settings


class PaystackError(Exception):
    """Raised when a Paystack call fails or isn't configured."""


class PaystackClient:
    def __init__(self) -> None:
        self.base = settings.paystack_base_url
        self.secret = settings.paystack_secret_key

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.secret}",
            "Content-Type": "application/json",
        }

    def _require_key(self) -> None:
        if not self.secret:
            raise PaystackError(
                "Paystack is not configured (set PAYSTACK_SECRET_KEY)."
            )

    def initialize(
        self,
        *,
        email: str,
        plan_code: str,
        amount: int,
        currency: str,
        callback_url: str,
        metadata: dict,
    ) -> dict:
        """Start a subscription checkout. Returns the transaction data
        (authorization_url + reference). Paystack requires the amount even when
        a plan is attached; it must match the plan's amount."""
        self._require_key()
        payload = {
            "email": email,
            "amount": amount,
            "currency": currency,
            "plan": plan_code,
            "callback_url": callback_url,
            "metadata": metadata,
        }
        try:
            with httpx.Client(timeout=20) as client:
                res = client.post(
                    f"{self.base}/transaction/initialize",
                    json=payload,
                    headers=self._headers(),
                )
            body = res.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PaystackError(f"Couldn't reach Paystack: {exc}") from exc
        if res.status_code >= 400 or not body.get("status"):
            raise PaystackError(body.get("message") or "Paystack initialize failed")
        return body["data"]

    def totals(self) -> dict:
        """Aggregate successful-transaction totals (for the admin dashboard).

        Returns Paystack's ``/transaction/totals`` data; amounts are in the
        smallest unit (kobo). Returns ``{}`` if billing isn't configured.
        """
        if not self.secret:
            return {}
        try:
            with httpx.Client(timeout=20) as client:
                res = client.get(
                    f"{self.base}/transaction/totals",
                    headers=self._headers(),
                )
            body = res.json()
        except (httpx.HTTPError, ValueError):
            return {}
        if res.status_code >= 400 or not body.get("status"):
            return {}
        return body.get("data", {})

    def list_transactions(
        self, *, page: int = 1, per_page: int = 50, status: str | None = None
    ) -> dict:
        """List transactions (admin payments view). Returns the full body
        ({data: [...], meta: {...}}), or empty if not configured."""
        if not self.secret:
            return {"data": [], "meta": {}}
        params: dict = {"perPage": per_page, "page": page}
        if status:
            params["status"] = status
        try:
            with httpx.Client(timeout=20) as client:
                res = client.get(
                    f"{self.base}/transaction",
                    params=params,
                    headers=self._headers(),
                )
            body = res.json()
        except (httpx.HTTPError, ValueError):
            return {"data": [], "meta": {}}
        if res.status_code >= 400 or not body.get("status"):
            return {"data": [], "meta": {}}
        return body

    def verify(self, reference: str) -> dict:
        """Verify a transaction by reference. Returns its data."""
        self._require_key()
        try:
            with httpx.Client(timeout=20) as client:
                res = client.get(
                    f"{self.base}/transaction/verify/{reference}",
                    headers=self._headers(),
                )
            body = res.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PaystackError(f"Couldn't reach Paystack: {exc}") from exc
        if res.status_code >= 400 or not body.get("status"):
            raise PaystackError(body.get("message") or "Paystack verify failed")
        return body["data"]
