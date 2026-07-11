"""Providers for the admin metrics feature."""

from fastapi import Depends
from supabase import Client

from app.admin.service import AdminService
from app.billing.client import PaystackClient
from app.billing.dependencies import get_paystack_client
from app.dependencies import get_db


#
def get_admin_service(
    db: Client = Depends(get_db),
    paystack: PaystackClient = Depends(get_paystack_client),
) -> AdminService:
    return AdminService(db, paystack)
