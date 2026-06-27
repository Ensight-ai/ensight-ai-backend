"""Providers wiring the billing feature for dependency injection."""

from fastapi import Depends

from app.auth.dependencies import get_auth_repository
from app.auth.repository import AuthRepository
from app.billing.client import PaystackClient
from app.billing.service import BillingService


def get_paystack_client() -> PaystackClient:
    return PaystackClient()


def get_billing_service(
    auth_repo: AuthRepository = Depends(get_auth_repository),
    client: PaystackClient = Depends(get_paystack_client),
) -> BillingService:
    return BillingService(auth_repo, client)
