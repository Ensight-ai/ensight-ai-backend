"""Providers wiring the integrations feature for dependency injection."""

from fastapi import Depends
from supabase import Client

from app.dependencies import get_db
from app.integrations.repository import GoogleConnectionRepository
from app.integrations.service import GoogleIntegrationService


def get_google_connection_repository(
    db: Client = Depends(get_db),
) -> GoogleConnectionRepository:
    return GoogleConnectionRepository(db)


def get_google_integration_service(
    repository: GoogleConnectionRepository = Depends(
        get_google_connection_repository
    ),
) -> GoogleIntegrationService:
    return GoogleIntegrationService(repository)
