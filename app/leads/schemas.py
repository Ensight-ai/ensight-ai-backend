"""Request/response models for sales-lead qualification.

A "lead" is what we infer from a finished (or ongoing) conversation between a
website visitor and an agent: how interested they seem, what they want, and any
contact details they volunteered. One lead per conversation.
"""

from datetime import datetime
from enum import Enum

from fastapi import Query
from pydantic import BaseModel, Field


class LeadStatus(str, Enum):
    """How promising a lead is. ``unqualified`` = not a sales lead at all."""

    hot = "hot"
    warm = "warm"
    cold = "cold"
    unqualified = "unqualified"


class LeadContact(BaseModel):
    """Contact details a visitor volunteered. All optional — we never invent."""

    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None


class LeadExtraction(BaseModel):
    """Structured output the model must return when reading a transcript.

    This is the schema the LLM is forced to fill (via structured output), not a
    stored row. Keeping ``contact_evidence`` lets the service drop any contact
    details that aren't actually backed by the transcript.
    """

    is_lead: bool = Field(
        description="True only if the visitor shows genuine interest in buying "
        "or using the business's product/service."
    )
    status: LeadStatus = Field(
        description="hot = ready to buy / asked to be contacted; warm = "
        "interested but exploring; cold = mild interest; unqualified = no "
        "buying intent (just support, browsing, or off-topic)."
    )
    score: int = Field(
        ge=0, le=100, description="0-100 how sales-ready this visitor is."
    )
    intent: str | None = Field(
        default=None, description="One short sentence: what the visitor wants."
    )
    summary: str | None = Field(
        default=None, description="A one-line summary of the conversation."
    )
    contact: LeadContact = Field(default_factory=LeadContact)
    contact_evidence: str | None = Field(
        default=None,
        description="Verbatim quote(s) from the transcript where the visitor "
        "gave their contact details. Null if they gave none.",
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="How confident you are in this assessment."
    )


class Lead(BaseModel):
    """A stored, qualified lead."""

    id: str
    user_id: str
    agent_id: str
    conversation_id: str
    status: LeadStatus
    score: int
    intent: str | None = None
    summary: str | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    confidence: float
    # True when the assessment is low-confidence and a human should review it.
    flagged: bool = False
    alert_sent_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LeadFilters:
    """Query params for filtering the leads list, injected via ``Depends()``.

    This is the "filter for good sales leads": narrow by status, a minimum
    score, a specific agent, or only the ones flagged for review.
    """

    def __init__(
        self,
        status: LeadStatus | None = Query(
            None, description="Only leads with this status (e.g. 'hot')."
        ),
        min_score: int = Query(
            0, ge=0, le=100, description="Only leads scoring at least this."
        ),
        agent_id: str | None = Query(
            None, description="Only leads from this agent."
        ),
        flagged: bool | None = Query(
            None, description="Filter by needs-review flag."
        ),
    ) -> None:
        self.status = status
        self.min_score = min_score
        self.agent_id = agent_id
        self.flagged = flagged
