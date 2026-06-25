"""Lead qualification business logic.

Ties together ownership checks, transcript building, the LLM extraction, a
light verification pass, and persistence.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.agents.service import AgentService
from app.conversations.message_repository import MessageRepository
from app.conversations.repository import ConversationRepository
from app.core.pagination import Page, PageParams
from app.leads.repository import LeadRepository
from app.leads.schemas import Lead, LeadExtraction, LeadFilters, LeadStatus

# Below this model-reported confidence, the lead is flagged for human review
# instead of being trusted outright.
_CONFIDENCE_THRESHOLD = 0.5


class LeadService:
    def __init__(
        self,
        leads: LeadRepository,
        conversations: ConversationRepository,
        messages: MessageRepository,
        agent_service: AgentService,
    ) -> None:
        self.leads = leads
        self.conversations = conversations
        self.messages = messages
        self.agent_service = agent_service

    # --- qualification ----------------------------------------------------
    def qualify_conversation(
        self, user_id: str, agent_id: str, conversation_id: str
    ) -> Lead:
        """Read a conversation and store what we infer about the lead."""
        self.agent_service.ensure_owned(agent_id, user_id)

        conversation = self.conversations.get_owned(conversation_id, agent_id)
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        transcript = self._build_transcript(conversation_id)
        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conversation has no messages to qualify.",
            )

        # Imported lazily so the leads list/get works without the LLM stack.
        from app.leads.qualifier import get_qualifier

        extraction = get_qualifier().extract(transcript)
        record = self._to_record(
            user_id, agent_id, conversation_id, extraction
        )
        saved = self.leads.upsert(record)
        if saved is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save lead",
            )
        return Lead(**saved)

    def _build_transcript(self, conversation_id: str) -> str:
        rows = self.messages.list_by_conversation(conversation_id)
        lines = []
        for row in rows:
            who = "Visitor" if row["role"] == "user" else "Assistant"
            lines.append(f"{who}: {row['content']}")
        return "\n".join(lines)

    @staticmethod
    def _to_record(
        user_id: str,
        agent_id: str,
        conversation_id: str,
        extraction: LeadExtraction,
    ) -> dict:
        """Apply verification, then shape the extraction into a table row.

        Verification: contact details survive only if the model cited evidence
        for them; low-confidence assessments are flagged for human review.
        """
        contact = extraction.contact
        if not extraction.contact_evidence:
            # No supporting quote -> don't trust any extracted contact details.
            name = email = phone = company = None
        else:
            name, email, phone = contact.name, contact.email, contact.phone
            company = contact.company

        lead_status = (
            extraction.status if extraction.is_lead else LeadStatus.unqualified
        )

        return {
            "user_id": user_id,
            "agent_id": agent_id,
            "conversation_id": conversation_id,
            "status": lead_status.value,
            "score": extraction.score,
            "intent": extraction.intent,
            "summary": extraction.summary,
            "name": name,
            "email": email,
            "phone": phone,
            "company": company,
            "confidence": extraction.confidence,
            "flagged": extraction.confidence < _CONFIDENCE_THRESHOLD,
        }

    # --- reads ------------------------------------------------------------
    def list_leads(
        self, user_id: str, filters: LeadFilters, params: PageParams
    ) -> Page[Lead]:
        rows, total = self.leads.list_filtered(
            user_id, filters, params.limit, params.offset
        )
        return Page(
            items=[Lead(**row) for row in rows],
            total=total,
            limit=params.limit,
            offset=params.offset,
        )

    def get_lead(self, lead_id: str, user_id: str) -> Lead:
        row = self.leads.get_owned(lead_id, user_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found"
            )
        return Lead(**row)
