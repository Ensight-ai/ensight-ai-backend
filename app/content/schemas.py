"""Request/response models for the content writing helper.

The business asks for a piece of marketing copy on a topic; we generate a
*draft* grounded in their own documents. Drafts are never published anywhere —
the owner reviews, edits, approves, and copies them out.
"""

from datetime import datetime
from enum import Enum

from fastapi import Query
from pydantic import BaseModel, Field


class ContentType(str, Enum):
    """The kind of copy to write."""

    blog_post = "blog_post"
    product_description = "product_description"
    email = "email"
    social_caption = "social_caption"
    faq_answer = "faq_answer"


class ContentStatus(str, Enum):
    draft = "draft"
    approved = "approved"


class ContentGenerateRequest(BaseModel):
    agent_id: str
    content_type: ContentType
    topic: str = Field(
        min_length=1, max_length=500, description="What to write about."
    )
    tone: str | None = Field(
        default=None, max_length=100, description="e.g. 'friendly', 'formal'."
    )
    extra_instructions: str | None = Field(
        default=None,
        max_length=1000,
        description="Any extra guidance for this piece.",
    )


class ContentUpdate(BaseModel):
    """Edit a draft's body and/or move it between draft and approved."""

    body: str | None = Field(default=None, min_length=1)
    status: ContentStatus | None = None


class ContentDraft(BaseModel):
    id: str
    user_id: str
    agent_id: str
    content_type: ContentType
    topic: str
    tone: str | None = None
    body: str
    status: ContentStatus
    # Whether the draft was grounded in the agent's documents (vs. generated
    # with no matching source material found).
    grounded: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContentFilters:
    """Query params for filtering the drafts list, injected via ``Depends()``."""

    def __init__(
        self,
        agent_id: str | None = Query(None, description="Only this agent's drafts."),
        content_type: ContentType | None = Query(
            None, description="Only this content type."
        ),
        status: ContentStatus | None = Query(
            None, description="draft or approved."
        ),
    ) -> None:
        self.agent_id = agent_id
        self.content_type = content_type
        self.status = status
