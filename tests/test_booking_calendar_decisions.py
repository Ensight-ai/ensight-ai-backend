from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from fastapi import HTTPException

from app.booking.schemas import RequestedTimeAvailability
from app.booking.service import BookingService
from app.chat.booking_tools import build_booking_tools


class _Integrations:
    def __init__(self, timezone_name: str = "Africa/Lagos") -> None:
        self.timezone_name = timezone_name
        self.token_requests = 0

    def get_timezone(self, _user_id: str) -> str:
        return self.timezone_name

    def get_valid_access_token(self, _user_id: str) -> str:
        self.token_requests += 1
        return "access-token"


class BookingServiceCalendarDecisionTests(TestCase):
    def setUp(self) -> None:
        self.integrations = _Integrations()
        self.service = BookingService(
            repository=None,
            integrations=self.integrations,
            agent_service=None,
        )

    @patch("app.booking.service.calendar_client.free_busy", return_value=[])
    def test_exact_free_time_is_available(self, free_busy) -> None:
        requested = (datetime.now() + timedelta(days=2)).replace(
            hour=8, minute=0, second=0, microsecond=0
        )

        result = self.service.check_time(
            "owner-1", requested, duration_minutes=30
        )

        self.assertTrue(result.available)
        self.assertEqual(result.timezone, "Africa/Lagos")
        self.assertEqual(result.start.utcoffset(), timedelta(hours=1))
        free_busy.assert_called_once_with(
            "access-token", result.start, result.start + timedelta(minutes=30)
        )

    @patch("app.booking.service.calendar_client.free_busy")
    def test_exact_busy_time_is_unavailable(self, free_busy) -> None:
        requested = datetime.now(timezone.utc) + timedelta(days=2)
        free_busy.return_value = [
            (requested - timedelta(minutes=5), requested + timedelta(minutes=10))
        ]

        result = self.service.check_time("owner-1", requested)

        self.assertFalse(result.available)
        self.assertEqual(result.reason, "The calendar is busy at that time.")

    @patch("app.booking.service.calendar_client.free_busy")
    def test_past_time_is_rejected_without_calendar_api_call(self, free_busy) -> None:
        result = self.service.check_time(
            "owner-1", datetime.now(timezone.utc) - timedelta(minutes=1)
        )

        self.assertFalse(result.available)
        self.assertEqual(result.reason, "That time has already passed.")
        self.assertEqual(self.integrations.token_requests, 0)
        free_busy.assert_not_called()

    @patch("app.booking.service.calendar_client.free_busy")
    def test_create_booking_rejects_past_time(self, free_busy) -> None:
        with self.assertRaises(HTTPException) as raised:
            self.service.create_booking(
                "owner-1",
                "agent-1",
                visitor_email="visitor@example.com",
                start_time=datetime.now(timezone.utc) - timedelta(minutes=1),
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(self.integrations.token_requests, 0)
        free_busy.assert_not_called()


class _ToolBookingService:
    def __init__(self, result: RequestedTimeAvailability) -> None:
        self.result = result
        self.requested_start: datetime | None = None

    def check_time(
        self, _user_id: str, start_time: datetime, *, duration_minutes: int
    ) -> RequestedTimeAvailability:
        self.requested_start = start_time
        return self.result


class BookingToolTests(TestCase):
    def test_exact_time_is_sent_to_calendar_service(self) -> None:
        start = datetime(2026, 8, 18, 8, 0, tzinfo=timezone.utc)
        service = _ToolBookingService(
            RequestedTimeAvailability(
                start=start,
                timezone="UTC",
                duration_minutes=30,
                available=True,
            )
        )
        availability_tool = build_booking_tools(
            service,
            user_id="owner-1",
            agent_id="agent-1",
            conversation_id="conversation-1",
            duration_minutes=30,
        )[0]

        output = availability_tool.invoke(
            {"requested_start_time": "2026-08-18T08:00:00+00:00"}
        )

        self.assertIn("AVAILABLE", output)
        self.assertIn("start_time=2026-08-18T08:00:00+00:00", output)
        self.assertEqual(service.requested_start, start)

    def test_invalid_exact_time_does_not_reach_calendar_service(self) -> None:
        start = datetime(2026, 8, 18, 8, 0, tzinfo=timezone.utc)
        service = _ToolBookingService(
            RequestedTimeAvailability(
                start=start,
                timezone="UTC",
                duration_minutes=30,
                available=True,
            )
        )
        availability_tool = build_booking_tools(
            service,
            user_id="owner-1",
            agent_id="agent-1",
            conversation_id=None,
            duration_minutes=30,
        )[0]

        output = availability_tool.invoke(
            {"requested_start_time": "tomorrow sometime"}
        )

        self.assertIn("wasn't a valid ISO 8601 time", output)
        self.assertIsNone(service.requested_start)
