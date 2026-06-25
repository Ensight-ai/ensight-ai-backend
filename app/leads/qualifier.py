"""LLM-backed lead extraction.

Reads a conversation transcript and returns a structured :class:`LeadExtraction`
using Gemini's structured-output (function-calling) mode, so the result is
always valid JSON matching our schema — no brittle text parsing.

Runs at ``temperature=0`` (deterministic) and is instructed to extract only
what the transcript supports, never to invent contact details. This is the
"verification" posture: the schema requires evidence for any contact info, and
the service drops anything unsupported.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from app.leads.schemas import LeadExtraction

if TYPE_CHECKING:  # avoid importing the heavy LLM stack at startup
    from langchain_google_vertexai import ChatVertexAI

_SYSTEM_PROMPT = (
    "You analyse a conversation between a website visitor and a business's AI "
    "assistant, and decide whether the visitor is a sales lead.\n\n"
    "Rules:\n"
    "- Judge ONLY from the transcript. Do not assume facts not present in it.\n"
    "- Extract contact details (name, email, phone, company) ONLY if the "
    "visitor actually stated them. If they did, put the exact supporting quote "
    "in 'contact_evidence'. If they gave none, leave contact fields null and "
    "'contact_evidence' null. Never guess or fabricate an email or phone.\n"
    "- 'is_lead' is true only for genuine interest in buying/using the product "
    "or service. People only asking for support, troubleshooting, or browsing "
    "are 'unqualified'.\n"
    "- Be conservative with 'score' and 'status'; reflect real uncertainty in "
    "'confidence'."
)


class LeadQualifier:
    """Wraps a Gemini model bound to the :class:`LeadExtraction` schema."""

    def __init__(self, model: str | None = None) -> None:
        from langchain_google_vertexai import ChatVertexAI

        llm: ChatVertexAI = ChatVertexAI(
            model=model or os.getenv("LLM_MODEL", "gemini-2.5-flash"),
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            temperature=0,
        )
        self._chain = llm.with_structured_output(LeadExtraction)

    def extract(self, transcript: str) -> LeadExtraction:
        return self._chain.invoke(
            [
                ("system", _SYSTEM_PROMPT),
                ("human", f"Conversation transcript:\n\n{transcript}"),
            ]
        )


# Lazily-created shared instance (the Vertex AI client is expensive to build).
_qualifier: LeadQualifier | None = None


def get_qualifier() -> LeadQualifier:
    global _qualifier
    if _qualifier is None:
        _qualifier = LeadQualifier()
    return _qualifier
