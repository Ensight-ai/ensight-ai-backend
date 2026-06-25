"""Providers wiring the booking feature for dependency injection."""

from fastapi import Depends
from supabase import Client

from app.agents.dependencies import get_agent_service
from app.agents.service import AgentService
from app.booking.repository import BookingRepository
from app.booking.service import BookingService
from app.dependencies import get_db
from app.integrations.dependencies import get_google_integration_service
from app.integrations.service import GoogleIntegrationService


def get_booking_repository(db: Client = Depends(get_db)) -> BookingRepository:
    return BookingRepository(db)


def get_booking_service(
    repository: BookingRepository = Depends(get_booking_repository),
    integrations: GoogleIntegrationService = Depends(
        get_google_integration_service
    ),
    agent_service: AgentService = Depends(get_agent_service),
) -> BookingService:
    return BookingService(repository, integrations, agent_service)
