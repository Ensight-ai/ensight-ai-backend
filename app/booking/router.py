"""Booking routes (owner-only): preview availability and list booked meetings.

The agent itself books during a chat via tools; these endpoints let the owner
verify their calendar connection and review what's been booked.
"""

from fastapi import APIRouter, Depends

from app.booking.dependencies import get_booking_service
from app.booking.schemas import AvailabilityResponse, Booking
from app.booking.service import BookingService
from app.core.pagination import Page, PageParams
from app.dependencies import get_current_user


router = APIRouter(prefix="/agents", tags=["booking"])


@router.get("/{agent_id}/availability", response_model=AvailabilityResponse)
def get_availability(
    agent_id: str,
    current_user=Depends(get_current_user),
    service: BookingService = Depends(get_booking_service),
):
    """Next open slots on the owner's calendar (uses this agent's duration)."""
    agent = service.agent_service.ensure_owned(agent_id, current_user.id)
    return service.get_availability(
        current_user.id,
        duration_minutes=agent.get("meeting_duration_minutes"),
    )


@router.get("/{agent_id}/bookings", response_model=Page[Booking])
def list_bookings(
    agent_id: str,
    current_user=Depends(get_current_user),
    params: PageParams = Depends(),
    service: BookingService = Depends(get_booking_service),
):
    return service.list_bookings(agent_id, current_user.id, params)
