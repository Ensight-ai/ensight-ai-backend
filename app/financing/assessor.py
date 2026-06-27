"""LLM-backed loan-readiness assessment.

Mirrors the lead qualifier: Gemini in structured-output mode returns a valid
:class:`LoanReadinessAssessment`, at ``temperature=0``, grounded only in the
business snapshot + owner-provided financials. It never invents revenue or
guarantees approval — it assesses readiness and recommends realistic options.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from app.financing.schemas import LoanReadinessAssessment

if TYPE_CHECKING:
    from langchain_google_vertexai import ChatVertexAI

_SYSTEM_PROMPT = (
    "You are an analyst for an SMB financial-access service. You assess how "
    "ready a small business is to access financing (loans, lines of credit, "
    "invoice financing, equipment leasing, merchant cash advances, micro-"
    "grants), using BOTH the owner-provided financials AND the business's "
    "platform activity as alternative data (customer conversations, qualified "
    "leads, booked meetings, content, time active).\n\n"
    "Rules:\n"
    "- Ground EVERYTHING in the data provided. Never invent revenue, history, "
    "or numbers the owner did not give. If a key financial is missing, list it "
    "as a gap rather than assuming it.\n"
    "- Treat platform activity as a demand/traction signal, not as revenue.\n"
    "- Recommend 2-4 realistic financing products fitted to this business, "
    "best fit first, and be honest about likelihood of qualifying.\n"
    "- 'application_summary' must be a concise, professional, lender-ready "
    "narrative the owner could submit — strictly grounded in the given data.\n"
    "- Be encouraging but truthful; do not promise approval."
)


class FinancingAssessor:
    def __init__(self, model: str | None = None) -> None:
        from langchain_google_vertexai import ChatVertexAI

        llm: ChatVertexAI = ChatVertexAI(
            model=model or os.getenv("LLM_MODEL", "gemini-2.5-flash"),
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            temperature=0,
        )
        self._chain = llm.with_structured_output(LoanReadinessAssessment)

    def assess(
        self, snapshot_text: str, intake_text: str
    ) -> LoanReadinessAssessment:
        return self._chain.invoke(
            [
                ("system", _SYSTEM_PROMPT),
                (
                    "human",
                    "Business activity on ensight (alternative data):\n"
                    f"{snapshot_text}\n\n"
                    "Owner-provided financials:\n"
                    f"{intake_text}",
                ),
            ]
        )


_assessor: FinancingAssessor | None = None


def get_assessor() -> FinancingAssessor:
    global _assessor
    if _assessor is None:
        _assessor = FinancingAssessor()
    return _assessor
