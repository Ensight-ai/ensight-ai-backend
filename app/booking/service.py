"""Booking business logic: availability and creating a Meet on the owner's calendar."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException, status

from app.agents.service import AgentService
from app.booking import calendar_client
from app.booking.repository import BookingRepository
from app.booking.schemas import (
    AvailabilityResponse,
    Booking,
    RequestedTimeAvailability,
    Slot,
)
from app.booking.slots import compute_free_slots
from app.core.config import settings
from app.core.pagination import Page, PageParams
from app.integrations.service import GoogleIntegrationService

_LABEL_FORMAT = "%a, %b %d, %I:%M %p"


class BookingService:
    def __init__(
        self,
        repository: BookingRepository,
        integrations: GoogleIntegrationService,
        agent_service: AgentService,
    ) -> None:
        self.repository = repository
        self.integrations = integrations
        self.agent_service = agent_service

    # --- availability -----------------------------------------------------
    def get_availability(
        self, user_id: str, *, duration_minutes: int | None = None, max_slots: int = 5
    ) -> AvailabilityResponse:
        duration = duration_minutes or settings.booking_meeting_minutes
        token = self.integrations.get_valid_access_token(user_id)
        tz = self.integrations.get_timezone(user_id)

        now = datetime.now(timezone.utc)
        # Widen the free/busy window past the business-day horizon to cover
        # intervening weekends.
        window_end = now + timedelta(days=settings.booking_lookahead_days + 5)
        try:
            busy = calendar_client.free_busy(token, now, window_end)
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Couldn't read the calendar's availability.",
            ) from exc

        starts = compute_free_slots(
            busy,
            now=now,
            timezone=tz,
            duration_minutes=duration,
            workday_start_hour=settings.booking_workday_start_hour,
            workday_end_hour=settings.booking_workday_end_hour,
            lookahead_business_days=settings.booking_lookahead_days,
            max_slots=max_slots,
        )
        slots = [Slot(start=s, label=s.strftime(_LABEL_FORMAT)) for s in starts]
        return AvailabilityResponse(
            timezone=tz, duration_minutes=duration, slots=slots
        )

    def check_time(
        self,
        user_id: str,
        start_time: datetime,
        *,
        duration_minutes: int | None = None,
    ) -> RequestedTimeAvailability:
        """Check one visitor-requested time against the owner's calendar.

        A time without an offset is interpreted in the calendar owner's
        timezone. Exact requests are not restricted to the suggestion window;
        the calendar itself decides whether the owner is free.
        """
        duration = duration_minutes or settings.booking_meeting_minutes
        tz_name = self.integrations.get_timezone(user_id)
        owner_tz = ZoneInfo(tz_name)

        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=owner_tz)
        else:
            start_time = start_time.astimezone(owner_tz)

        if start_time <= datetime.now(timezone.utc):
            return RequestedTimeAvailability(
                start=start_time,
                timezone=tz_name,
                duration_minutes=duration,
                available=False,
                reason="That time has already passed.",
            )

        token = self.integrations.get_valid_access_token(user_id)
        end_time = start_time + timedelta(minutes=duration)
        try:
            busy = calendar_client.free_busy(token, start_time, end_time)
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Couldn't check that time on the calendar.",
            ) from exc

        available = not any(
            start_time < busy_end and busy_start < end_time
            for busy_start, busy_end in busy
        )
        return RequestedTimeAvailability(
            start=start_time,
            timezone=tz_name,
            duration_minutes=duration,
            available=available,
            reason=None if available else "The calendar is busy at that time.",
        )

    # --- booking ----------------------------------------------------------
    def create_booking(
        self,
        user_id: str,
        agent_id: str,
        *,
        visitor_email: str,
        start_time: datetime,
        visitor_name: str | None = None,
        visitor_phone: str | None = None,
        conversation_id: str | None = None,
        duration_minutes: int | None = None,
    ) -> Booking:
        duration = duration_minutes or settings.booking_meeting_minutes
        tz = self.integrations.get_timezone(user_id)

        # Interpret a naive start time as being in the owner's timezone.
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=ZoneInfo(tz))
        else:
            start_time = start_time.astimezone(ZoneInfo(tz))
        if start_time <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That meeting time has already passed.",
            )
        token = self.integrations.get_valid_access_token(user_id)
        end_time = start_time + timedelta(minutes=duration)

        # Re-check the slot is still free right before booking (avoid races).
        try:
            busy = calendar_client.free_busy(token, start_time, end_time)
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Couldn't verify the calendar before booking.",
            ) from exc
        if any(start_time < b_end and b_start < end_time for b_start, b_end in busy):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That time was just taken. Please pick another.",
            )

        who = visitor_name or visitor_email
        try:
            event = calendar_client.create_event(
                token,
                summary=f"Meeting with {who}",
                description=_event_description(
                    visitor_name, visitor_email, visitor_phone
                ),
                start=start_time,
                end=end_time,
                timezone=tz,
                attendee_emails=[visitor_email],
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Couldn't create the calendar event.",
            ) from exc

        saved = self.repository.create(
            {
                "user_id": user_id,
                "agent_id": agent_id,
                "conversation_id": conversation_id,
                "visitor_name": visitor_name,
                "visitor_email": visitor_email,
                "visitor_phone": visitor_phone,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "meet_link": event.get("meet_link"),
                "event_id": event.get("event_id"),
                "status": "confirmed",
            }
        )
        if saved is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save booking",
            )
        return Booking(**saved)

    # --- reads (owner-gated) ----------------------------------------------
    def list_bookings(
        self, agent_id: str, user_id: str, params: PageParams
    ) -> Page[Booking]:
        self.agent_service.ensure_owned(agent_id, user_id)
        rows, total = self.repository.page_by_agent(
            agent_id, params.limit, params.offset
        )
        return Page(
            items=[Booking(**row) for row in rows],
            total=total,
            limit=params.limit,
            offset=params.offset,
        )


def _event_description(
    name: str | None, email: str, phone: str | None
) -> str:
    lines = ["Booked via your ensight agent.", ""]
    if name:
        lines.append(f"Name: {name}")
    lines.append(f"Email: {email}")
    if phone:
        lines.append(f"Phone: {phone}")
    return "\n".join(lines)
