"""Conversation browsing routes (owner-only)."""

from fastapi import APIRouter, Depends

from app.conversations.dependencies import get_conversation_service
from app.conversations.schemas import ConversationDetail, ConversationSummary
from app.conversations.service import ConversationService
from app.core.pagination import Page, PageParams
from app.dependencies import get_current_user


class ConversationController:
    def __init__(
        self, service: ConversationService = Depends(get_conversation_service)
    ) -> None:
        self.service = service

    def list(
        self, agent_id: str, user_id: str, params: PageParams
    ) -> Page[ConversationSummary]:
        return self.service.list_conversations(agent_id, user_id, params)

    def get(
        self, agent_id: str, conversation_id: str, user_id: str
    ) -> ConversationDetail:
        return self.service.get_conversation(agent_id, conversation_id, user_id)


router = APIRouter(prefix="/agents", tags=["conversations"])


@router.get(
    "/{agent_id}/conversations", response_model=Page[ConversationSummary]
)
def list_conversations(
    agent_id: str,
    current_user=Depends(get_current_user),
    params: PageParams = Depends(),
    controller: ConversationController = Depends(),
):
    return controller.list(agent_id, current_user.id, params)


@router.get(
    "/{agent_id}/conversations/{conversation_id}",
    response_model=ConversationDetail,
)
def get_conversation(
    agent_id: str,
    conversation_id: str,
    current_user=Depends(get_current_user),
    controller: ConversationController = Depends(),
):
    return controller.get(agent_id, conversation_id, current_user.id)
