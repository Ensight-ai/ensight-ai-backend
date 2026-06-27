"""Models for the AI Financial Access Assistant.

ensight already knows a business — what it sells (ingested docs), customer
demand (conversations), lead quality, and booked meetings. This module turns
that *alternative data* into a loan-readiness assessment, recommended financing
options, and a lender-ready application summary, so small businesses that lack
formal credit history can still access finance.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class BusinessSnapshot(BaseModel):
    """Activity ensight has observed for a business — the alternative-data
    signal behind the assessment. Aggregated automatically; not user-entered."""

    agents: int
    conversations: int
    unique_visitors: int
    qualified_leads: int
    hot_leads: int
    meetings_booked: int
    content_pieces: int
    first_activity: datetime | None = None
    last_activity: datetime | None = None
    # A few recent visitor questions — a window into real customer demand.
    demand_signals: list[str] = Field(default_factory=list)


class FinancingIntake(BaseModel):
    """The handful of financials ensight can't infer, asked of the owner.

    All optional: the assistant works with whatever is provided and lists the
    rest as gaps rather than blocking.
    """

    monthly_revenue: float | None = Field(
        default=None, ge=0, description="Average monthly revenue."
    )
    currency: str = Field(default="USD", max_length=8)
    time_in_business_months: int | None = Field(default=None, ge=0)
    employees: int | None = Field(default=None, ge=0)
    amount_sought: float | None = Field(
        default=None, ge=0, description="How much financing they want."
    )
    purpose: str | None = Field(
        default=None, max_length=500, description="What the funds are for."
    )
    country: str | None = Field(default=None, max_length=80)


class Likelihood(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class FinancingProduct(BaseModel):
    """A recommended financing option fitted to this business."""

    name: str = Field(description="e.g. 'Working-capital line of credit'.")
    description: str = Field(description="One line on what it is.")
    why_fit: str = Field(description="Why it suits THIS business specifically.")
    typical_amount: str | None = Field(
        default=None, description="Rough amount range, e.g. '$2k–$15k'."
    )
    likelihood: Likelihood = Field(
        description="How likely this business is to qualify, given the data."
    )


class LoanReadinessAssessment(BaseModel):
    """Structured output the model must return — never free text."""

    readiness_score: int = Field(
        ge=0, le=100, description="0-100 overall loan/finance readiness."
    )
    tier: str = Field(
        description="A short label: 'strong', 'emerging', or 'early-stage'."
    )
    strengths: list[str] = Field(
        description="What makes this business fundable, grounded in the data."
    )
    gaps: list[str] = Field(
        description="What's missing or would strengthen an application."
    )
    recommended_products: list[FinancingProduct] = Field(
        description="2-4 realistic financing options, best fit first."
    )
    application_summary: str = Field(
        description="A concise, lender-ready narrative the owner can submit. "
        "Grounded ONLY in the provided data; never invents financials."
    )
    next_steps: list[str] = Field(
        description="Concrete actions to become (more) loan-ready."
    )


class FinancingResult(BaseModel):
    """Full response: the data we used + the assessment."""

    snapshot: BusinessSnapshot
    intake: FinancingIntake
    assessment: LoanReadinessAssessment
