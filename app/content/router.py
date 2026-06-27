"""Content routes: generate, list/filter, fetch, edit and delete drafts (owner-only)."""

from fastapi import APIRouter, Depends, status

from app.content.dependencies import get_content_service
from app.content.schemas import (
    ContentDraft,
    ContentFilters,
    ContentGenerateRequest,
    ContentUpdate,
)
from app.content.service import ContentService
from app.core.pagination import Page, PageParams
from app.core.plan_guard import require_feature
from app.core.plans import Feature
from app.dependencies import get_current_user


class ContentController:
    def __init__(
        self, service: ContentService = Depends(get_content_service)
    ) -> None:
        self.service = service

    def generate(
        self, user_id: str, payload: ContentGenerateRequest
    ) -> ContentDraft:
        return self.service.generate(user_id, payload)

    def list(
        self, user_id: str, filters: ContentFilters, params: PageParams
    ) -> Page[ContentDraft]:
        return self.service.list_drafts(user_id, filters, params)

    def get(self, draft_id: str, user_id: str) -> ContentDraft:
        return self.service.get_draft(draft_id, user_id)

    def update(
        self, draft_id: str, user_id: str, payload: ContentUpdate
    ) -> ContentDraft:
        return self.service.update_draft(draft_id, user_id, payload)

    def delete(self, draft_id: str, user_id: str) -> None:
        self.service.delete_draft(draft_id, user_id)


router = APIRouter(prefix="/content", tags=["content"])


@router.post(
    "/generate", response_model=ContentDraft, status_code=status.HTTP_201_CREATED
)
def generate_content(
    payload: ContentGenerateRequest,
    current_user=Depends(require_feature(Feature.content)),
    controller: ContentController = Depends(),
):
    return controller.generate(current_user.id, payload)


@router.get("", response_model=Page[ContentDraft])
def list_content(
    current_user=Depends(get_current_user),
    filters: ContentFilters = Depends(),
    params: PageParams = Depends(),
    controller: ContentController = Depends(),
):
    return controller.list(current_user.id, filters, params)


@router.get("/{draft_id}", response_model=ContentDraft)
def get_content(
    draft_id: str,
    current_user=Depends(get_current_user),
    controller: ContentController = Depends(),
):
    return controller.get(draft_id, current_user.id)


@router.patch("/{draft_id}", response_model=ContentDraft)
def update_content(
    draft_id: str,
    payload: ContentUpdate,
    current_user=Depends(get_current_user),
    controller: ContentController = Depends(),
):
    return controller.update(draft_id, current_user.id, payload)


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_content(
    draft_id: str,
    current_user=Depends(get_current_user),
    controller: ContentController = Depends(),
):
    controller.delete(draft_id, current_user.id)
