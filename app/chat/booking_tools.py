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
    def check_availability(requested_start_time: str = "") -> str:
        """Check the owner's Google Calendar before discussing availability.

        When the visitor gives an exact date/time, pass it as an ISO 8601 value
        in requested_start_time. A value without an offset is interpreted in
        the calendar owner's timezone. Otherwise leave it empty to get the
        next open meeting times. Never invent availability.
        """
        if requested_start_time:
            try:
                requested = datetime.fromisoformat(
                    requested_start_time.replace("Z", "+00:00")
                )
            except (TypeError, ValueError):
                return (
                    "requested_start_time wasn't a valid ISO 8601 time. Convert "
                    "the visitor's requested date and time and try again."
                )
            try:
                result = booking_service.check_time(
                    user_id,
                    requested,
                    duration_minutes=duration_minutes,
                )
            except HTTPException as exc:
                return f"Could not check that requested time: {exc.detail}"

            label = result.start.strftime("%a, %b %d, %Y at %I:%M %p")
            if result.available:
                return (
                    f"AVAILABLE: {label} ({result.timezone}) is open for a "
                    f"{result.duration_minutes}-minute meeting. "
                    f"[start_time={result.start.isoformat()}]"
                )
            return f"NOT AVAILABLE: {label} ({result.timezone}). {result.reason}"

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
