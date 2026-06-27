"""Billing routes: start a subscription, verify it, receive webhooks."""

from fastapi import APIRouter, Depends, Header, Request

from app.billing.dependencies import get_billing_service
from app.billing.schemas import CheckoutRequest, CheckoutResponse, VerifyResponse
from app.billing.service import BillingService
from app.dependencies import get_current_user

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(
    payload: CheckoutRequest,
    current_user=Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    return service.checkout(current_user.id, current_user.email, payload.plan)


@router.get("/verify/{reference}", response_model=VerifyResponse)
def verify(
    reference: str,
    current_user=Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    return service.verify(reference, current_user.id)


@router.post("/webhook")
async def webhook(
    request: Request,
    x_paystack_signature: str = Header(default=""),
    service: BillingService = Depends(get_billing_service),
):
    # Signature is computed over the raw body, so read it before parsing.
    raw = await request.body()
    service.handle_webhook(raw, x_paystack_signature)
    return {"status": "ok"}
