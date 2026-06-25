"""Providers wiring the content feature for dependency injection."""

from fastapi import Depends
from supabase import Client

from app.agents.dependencies import get_agent_service
from app.agents.service import AgentService
from app.content.repository import ContentRepository
from app.content.service import ContentService
from app.dependencies import get_db


def get_content_repository(db: Client = Depends(get_db)) -> ContentRepository:
    return ContentRepository(db)


def get_content_service(
    repository: ContentRepository = Depends(get_content_repository),
    agent_service: AgentService = Depends(get_agent_service),
) -> ContentService:
    return ContentService(repository, agent_service)
