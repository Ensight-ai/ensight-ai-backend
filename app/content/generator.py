"""LLM-backed marketing-copy generation, grounded in the agent's documents.

Unlike the support agent (which runs at temperature 0), content generation uses
a higher temperature for more natural, varied copy — but is still grounded:
relevant chunks from the business's own documents are injected as context so
claims stay accurate.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from app.content.schemas import ContentType

if TYPE_CHECKING:  # avoid importing the heavy LLM stack at startup
    from langchain_google_vertexai import ChatVertexAI

# Per-type guidance appended to the system prompt.
_TYPE_GUIDANCE: dict[ContentType, str] = {
    ContentType.blog_post: "Write an engaging blog post with a clear structure "
    "(intro, a few short sections, and a closing line).",
    ContentType.product_description: "Write a concise, persuasive product "
    "description that highlights benefits, not just features.",
    ContentType.email: "Write a short marketing email with a compelling "
    "subject line on its first line, then the body.",
    ContentType.social_caption: "Write a punchy social media caption (1-3 short "
    "sentences). You may suggest a few relevant hashtags at the end.",
    ContentType.faq_answer: "Write a clear, friendly answer to this FAQ, in 1-2 "
    "short paragraphs.",
}

_SYSTEM_PROMPT = (
    "You are a marketing copywriter for this business. Write in the first "
    "person on the business's behalf (\"we\", \"our\"). {type_guidance}\n\n"
    "Ground your writing in the business context below — keep facts (names, "
    "prices, features, claims) consistent with it and do not invent specifics "
    "that aren't supported. If the context is empty, write something useful and "
    "general without fabricating concrete details.{tone}\n\n"
    "Return only the requested copy — no preamble, no explanations, no "
    "markdown headings.\n\n"
    "Business context:\n{context}"
)


class ContentGenerator:
    def __init__(self, temperature: float = 0.7) -> None:
        from langchain_google_vertexai import ChatVertexAI

        self.llm: ChatVertexAI = ChatVertexAI(
            model=os.getenv("LLM_MODEL", "gemini-2.5-flash"),
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            temperature=temperature,
        )

    def generate(
        self,
        *,
        content_type: ContentType,
        topic: str,
        context: str,
        tone: str | None = None,
        extra_instructions: str | None = None,
    ) -> str:
        system = _SYSTEM_PROMPT.format(
            type_guidance=_TYPE_GUIDANCE[content_type],
            tone=f" Write in a {tone} tone." if tone else "",
            context=context or "(no documents found)",
        )
        human = f"Topic: {topic}"
        if extra_instructions:
            human += f"\n\nAdditional instructions: {extra_instructions}"

        result = self.llm.invoke([("system", system), ("human", human)])
        return result.content if isinstance(result.content, str) else str(
            result.content
        )


# Lazily-created shared instance (the Vertex AI client is expensive to build).
_generator: ContentGenerator | None = None


def get_generator() -> ContentGenerator:
    global _generator
    if _generator is None:
        _generator = ContentGenerator()
    return _generator
