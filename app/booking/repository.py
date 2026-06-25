"""Data access for the ``bookings`` table."""

from supabase import Client


class BookingRepository:
    _TABLE = "bookings"

    def __init__(self, db: Client) -> None:
        self.db = db

    def create(self, record: dict) -> dict | None:
        result = self.db.table(self._TABLE).insert(record).execute()
        return result.data[0] if result.data else None

    def page_by_agent(
        self, agent_id: str, limit: int, offset: int
    ) -> tuple[list[dict], int]:
        result = (
            self.db.table(self._TABLE)
            .select("*", count="exact")
            .eq("agent_id", agent_id)
            .order("start_time", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return result.data, result.count or 0
