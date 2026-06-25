"""Models for availability and bookings."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr


class Slot(BaseModel):
    """A suggestable open meeting time."""

    start: datetime
    # Human-friendly label in the owner's timezone, e.g. "Tue, Jul 1, 2:00 PM".
    label: str


class AvailabilityResponse(BaseModel):
    timezone: str
    duration_minutes: int
    slots: list[Slot]


class BookingStatus(str, Enum):
    confirmed = "confirmed"
    cancelled = "cancelled"


class Booking(BaseModel):
    id: str
    user_id: str
    agent_id: str
    conversation_id: str | None = None
    visitor_name: str | None = None
    visitor_email: EmailStr
    visitor_phone: str | None = None
    start_time: datetime
    end_time: datetime
    meet_link: str | None = None
    event_id: str | None = None
    status: BookingStatus
    created_at: datetime | None = None
