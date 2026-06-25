"""Builds the LangChain tools the agent uses to book meetings during a chat.

The tools are closures bound to one conversation (owner, agent, conversation,
meeting length), so the model never has to handle identity — it just calls
``check_availability`` and ``book_meeting``. Tool errors are caught and returned
as text so the model can recover gracefully instead of crashing the turn.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from langchain_core.tools import tool

from app.booking.service import BookingService


def build_booking_tools(
    booking_service: BookingService,
    *,
    user_id: str,
    agent_id: str,
    conversation_id: str | None,
    duration_minutes: int | None,
) -> list:
    @tool
    def check_availability() -> str:
        """Get the business's next open meeting times. Always call this before
        suggesting any times — never invent availability."""
        try:
            result = booking_service.get_availability(
                user_id, duration_minutes=duration_minutes
            )
        except HTTPException as exc:
            return f"Could not check availability: {exc.detail}"
        if not result.slots:
            return "There are no open slots in the next few business days."
        lines = [f"Open {result.duration_minutes}-minute slots ({result.timezone}):"]
        for slot in result.slots:
            # The model should pass start_time back verbatim when booking.
            lines.append(f"- {slot.label}  [start_time={slot.start.isoformat()}]")
        return "\n".join(lines)

    @tool
    def book_meeting(
        visitor_name: str,
        visitor_email: str,
        start_time: str,
        visitor_phone: str = "",
    ) -> str:
        """Book a meeting on the business's calendar and invite the visitor.

        start_time must be one of the exact start_time values returned by
        check_availability (ISO 8601). Requires the visitor's name and email.
        """
        try:
            start = datetime.fromisoformat(start_time)
        except ValueError:
            return (
                "start_time wasn't a valid time. Call check_availability and use "
                "one of its start_time values exactly."
            )
        try:
            booking = booking_service.create_booking(
                user_id,
                agent_id,
                visitor_email=visitor_email,
                start_time=start,
                visitor_name=visitor_name or None,
                visitor_phone=visitor_phone or None,
                conversation_id=conversation_id,
                duration_minutes=duration_minutes,
            )
        except HTTPException as exc:
            return f"Could not book the meeting: {exc.detail}"

        link = booking.meet_link or "(link will be in the calendar invite)"
        return (
            f"Booked for {booking.start_time.strftime('%a, %b %d, %I:%M %p')}. "
            f"A calendar invite was emailed to {booking.visitor_email}. "
            f"Google Meet link: {link}"
        )

    return [check_availability, book_meeting]
