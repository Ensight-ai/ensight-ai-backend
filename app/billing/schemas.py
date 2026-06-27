"""Request/response models for Paystack billing."""

from pydantic import BaseModel

from app.auth.schemas import Plan


class CheckoutRequest(BaseModel):
    # Which plan the user wants to subscribe to.
    plan: Plan


class CheckoutResponse(BaseModel):
    # Where to send the user's browser to complete payment.
    authorization_url: str
    reference: str


class VerifyResponse(BaseModel):
    status: str  # "success" / "failed" / "abandoned" ...
    plan: Plan | None = None
