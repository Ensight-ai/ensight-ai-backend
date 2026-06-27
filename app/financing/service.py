"""Financial-access business logic: snapshot the business, then assess it."""

from __future__ import annotations

from app.conversations.message_repository import MessageRepository
from app.financing.repository import FinancingRepository
from app.financing.schemas import (
    BusinessSnapshot,
    FinancingIntake,
    FinancingResult,
)


class FinancingService:
    def __init__(
        self, repo: FinancingRepository, messages: MessageRepository
    ) -> None:
        self.repo = repo
        self.messages = messages

    def build_snapshot(self, user_id: str) -> BusinessSnapshot:
        agent_ids = self.repo.agent_ids(user_id)
        conversations, visitors, first, last = self.repo.conversation_stats(
            agent_ids
        )
        qualified, hot = self.repo.lead_counts(user_id)

        demand: list[str] = []
        for agent_id in agent_ids[:5]:
            demand.extend(self.messages.recent_questions(agent_id, 5))
            if len(demand) >= 8:
                break

        return BusinessSnapshot(
            agents=len(agent_ids),
            conversations=conversations,
            unique_visitors=visitors,
            qualified_leads=qualified,
            hot_leads=hot,
            meetings_booked=self.repo.booking_count(agent_ids),
            content_pieces=self.repo.content_count(agent_ids),
            first_activity=first,
            last_activity=last,
            demand_signals=demand[:8],
        )

    def assess(self, user_id: str, intake: FinancingIntake) -> FinancingResult:
        snapshot = self.build_snapshot(user_id)

        # Imported lazily so snapshot/reads work without the LLM stack loaded.
        from app.financing.assessor import get_assessor

        assessment = get_assessor().assess(
            self._snapshot_text(snapshot), self._intake_text(intake)
        )
        return FinancingResult(
            snapshot=snapshot, intake=intake, assessment=assessment
        )

    @staticmethod
    def _snapshot_text(s: BusinessSnapshot) -> str:
        lines = [
            f"- Active AI agents: {s.agents}",
            f"- Customer conversations handled: {s.conversations}",
            f"- Unique visitors reached: {s.unique_visitors}",
            f"- Qualified sales leads: {s.qualified_leads} (hot: {s.hot_leads})",
            f"- Meetings booked with prospects: {s.meetings_booked}",
            f"- Marketing content pieces produced: {s.content_pieces}",
        ]
        if s.first_activity:
            lines.append(f"- Active on the platform since: {s.first_activity.date()}")
        if s.demand_signals:
            lines.append("- Recent customer questions (demand signals):")
            lines.extend(f"    • {q}" for q in s.demand_signals)
        return "\n".join(lines)

    @staticmethod
    def _intake_text(i: FinancingIntake) -> str:
        cur = i.currency
        parts = [
            f"- Monthly revenue: {i.monthly_revenue} {cur}"
            if i.monthly_revenue is not None
            else "- Monthly revenue: not provided",
            f"- Time in business: {i.time_in_business_months} months"
            if i.time_in_business_months is not None
            else "- Time in business: not provided",
        ]
        if i.employees is not None:
            parts.append(f"- Employees: {i.employees}")
        if i.amount_sought is not None:
            parts.append(f"- Financing sought: {i.amount_sought} {cur}")
        if i.purpose:
            parts.append(f"- Purpose of financing: {i.purpose}")
        if i.country:
            parts.append(f"- Country: {i.country}")
        return "\n".join(parts)
