"""Content writing-helper business logic (owner-gated).

Generates a draft grounded in the agent's documents, then stores it for the
owner to review/edit/approve. Nothing is published anywhere.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.agents.service import AgentService
from app.content.repository import ContentRepository
from app.content.schemas import (
    ContentDraft,
    ContentFilters,
    ContentGenerateRequest,
    ContentStatus,
    ContentUpdate,
)
from app.core.pagination import Page, PageParams


class ContentService:
    def __init__(
        self, repository: ContentRepository, agent_service: AgentService
    ) -> None:
        self.repository = repository
        self.agent_service = agent_service

    def generate(
        self, user_id: str, payload: ContentGenerateRequest
    ) -> ContentDraft:
        self.agent_service.ensure_owned(payload.agent_id, user_id)

        # Imported lazily so content list/get works without the LLM stack.
        from app.content.generator import get_generator
        from rag_bot.rag_engine import get_engine

        # Ground the draft in the agent's own documents (may be empty).
        context = get_engine().retrieve_context(
            payload.topic, user_id=user_id, agent_id=payload.agent_id
        )
        body = get_generator().generate(
            content_type=payload.content_type,
            topic=payload.topic,
            context=context,
            tone=payload.tone,
            extra_instructions=payload.extra_instructions,
        )

        record = {
            "user_id": user_id,
            "agent_id": payload.agent_id,
            "content_type": payload.content_type.value,
            "topic": payload.topic,
            "tone": payload.tone,
            "body": body,
            "status": ContentStatus.draft.value,
            "grounded": bool(context),
        }
        created = self.repository.create(record)
        if created is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save draft",
            )
        return ContentDraft(**created)

    def list_drafts(
        self, user_id: str, filters: ContentFilters, params: PageParams
    ) -> Page[ContentDraft]:
        rows, total = self.repository.list_filtered(
            user_id, filters, params.limit, params.offset
        )
        return Page(
            items=[ContentDraft(**row) for row in rows],
            total=total,
            limit=params.limit,
            offset=params.offset,
        )

    def get_draft(self, draft_id: str, user_id: str) -> ContentDraft:
        row = self.repository.get_owned(draft_id, user_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found"
            )
        return ContentDraft(**row)

    def update_draft(
        self, draft_id: str, user_id: str, payload: ContentUpdate
    ) -> ContentDraft:
        existing = self.get_draft(draft_id, user_id)

        updates: dict = {}
        if payload.body is not None:
            updates["body"] = payload.body
        if payload.status is not None:
            updates["status"] = payload.status.value
        if not updates:
            return existing

        updated = self.repository.update(draft_id, updates)
        return ContentDraft(**updated)

    def delete_draft(self, draft_id: str, user_id: str) -> None:
        self.get_draft(draft_id, user_id)  # 404s if not owned
        self.repository.delete(draft_id)
