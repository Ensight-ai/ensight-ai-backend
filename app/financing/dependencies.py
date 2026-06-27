"""Providers wiring the financing feature for dependency injection."""

from fastapi import Depends
from supabase import Client

from app.conversations.dependencies import get_message_repository
from app.conversations.message_repository import MessageRepository
from app.dependencies import get_db
from app.financing.repository import FinancingRepository
from app.financing.service import FinancingService


def get_financing_repository(db: Client = Depends(get_db)) -> FinancingRepository:
    return FinancingRepository(db)


def get_financing_service(
    repo: FinancingRepository = Depends(get_financing_repository),
    messages: MessageRepository = Depends(get_message_repository),
) -> FinancingService:
    return FinancingService(repo, messages)
