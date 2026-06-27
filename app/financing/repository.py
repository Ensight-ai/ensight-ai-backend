"""Aggregate a business's ensight footprint into financing signals.

Most ensight data is agent-scoped, so we first resolve the owner's agent ids,
then roll up conversations, bookings, content and leads across them.
"""

from supabase import Client


class FinancingRepository:
    def __init__(self, db: Client) -> None:
        self.db = db

    def agent_ids(self, user_id: str) -> list[str]:
        result = (
            self.db.table("agents")
            .select("id")
            .eq("user_id", user_id)
            .execute()
        )
        return [row["id"] for row in result.data]

    def conversation_stats(
        self, agent_ids: list[str]
    ) -> tuple[int, int, str | None, str | None]:
        """Returns (total, unique_visitors, first_activity, last_activity)."""
        if not agent_ids:
            return 0, 0, None, None
        result = (
            self.db.table("conversations")
            .select("visitor_id,started_at")
            .in_("agent_id", agent_ids)
            .execute()
        )
        rows = result.data
        visitors = {r["visitor_id"] for r in rows if r.get("visitor_id")}
        dates = [r["started_at"] for r in rows if r.get("started_at")]
        return (
            len(rows),
            len(visitors),
            min(dates) if dates else None,
            max(dates) if dates else None,
        )

    def booking_count(self, agent_ids: list[str]) -> int:
        if not agent_ids:
            return 0
        result = (
            self.db.table("bookings")
            .select("id", count="exact")
            .in_("agent_id", agent_ids)
            .eq("status", "confirmed")
            .execute()
        )
        return result.count or 0

    def content_count(self, agent_ids: list[str]) -> int:
        if not agent_ids:
            return 0
        result = (
            self.db.table("content_drafts")
            .select("id", count="exact")
            .in_("agent_id", agent_ids)
            .execute()
        )
        return result.count or 0

    def lead_counts(self, user_id: str) -> tuple[int, int]:
        """Returns (qualified_leads, hot_leads)."""
        result = (
            self.db.table("leads")
            .select("status")
            .eq("user_id", user_id)
            .execute()
        )
        rows = result.data
        qualified = sum(1 for r in rows if r.get("status") != "unqualified")
        hot = sum(1 for r in rows if r.get("status") == "hot")
        return qualified, hot
