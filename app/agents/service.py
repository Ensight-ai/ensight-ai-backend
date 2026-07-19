"""Agent business logic: ownership, plan gating, CRUD, document ingestion."""

import os
import shutil
import tempfile

from fastapi import HTTPException, UploadFile, status

from app.agents.repository import AgentRepository
from app.agents.schemas import Agent, AgentCreate, AgentUpdate, Capability, IngestResponse
from app.auth.service import AuthService
from app.core.pagination import Page, PageParams
from app.core.plans import (
    Feature,
    agent_limit,
    is_capability_allowed,
    is_feature_allowed,
)
from app.core.security import generate_public_key


class AgentService:
    def __init__(
        self, repository: AgentRepository, auth_service: AuthService
    ) -> None:
        self.repository = repository
        self.auth_service = auth_service

    def ensure_owned(self, agent_id: str, user_id: str) -> dict:
        """Return the agent if owned by ``user_id``, else 404.

        Reused by other features (analytics, conversations, exports) as the
        ownership gate.
        """
        agent = self.repository.get_owned(agent_id, user_id)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
            )
        return agent

    def _ensure_capability_allowed(
        self, user_id: str, capability: Capability
    ) -> None:
        plan = self.auth_service.get_plan(user_id)
        if not is_capability_allowed(plan, capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Your '{plan.value}' plan does not allow "
                    f"'{capability.value}' agents."
                ),
            )

    def _ensure_feature_allowed(self, user_id: str, feature: Feature) -> None:
        plan = self.auth_service.get_plan(user_id)
        if not is_feature_allowed(plan, feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Your '{plan.value}' plan does not include "
                    f"'{feature.value}'. Upgrade to unlock it."
                ),
            )

    def create_agent(self, user_id: str, payload: AgentCreate) -> Agent:
        plan = self.auth_service.get_plan(user_id)

        if not is_capability_allowed(plan, payload.capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Your '{plan.value}' plan does not allow "
                    f"'{payload.capability.value}' agents."
                ),
            )

        limit = agent_limit(plan)
        if self.repository.count_by_user(user_id) >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Your '{plan.value}' plan allows up to {limit} "
                    f"agent{'s' if limit != 1 else ''}. Upgrade to add more."
                ),
            )

        if payload.booking_enabled and not is_feature_allowed(
            plan, Feature.booking
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Meeting booking isn't included in your '{plan.value}' "
                    "plan. Upgrade to enable it."
                ),
            )

        record = {
            "user_id": user_id,
            "name": payload.name,
            "capability": payload.capability.value,
            "background_color": payload.background_color,
            "position": payload.position.value,
            "greeting": payload.greeting,
            "booking_enabled": payload.booking_enabled,
            "meeting_duration_minutes": payload.meeting_duration_minutes,
            "public_key": generate_public_key(),
        }
        created = self.repository.create(record)
        if created is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create agent",
            )

        # Notify the owner by email — best-effort, never blocks agent creation.
        try:
            from app.core import mailer

            email = self.auth_service.get_profile(user_id).email
            if email:
                mailer.send_agent_created_email(email, payload.name)
        except Exception:
            pass

        return Agent(**created)

    def list_agents(self, user_id: str, params: PageParams) -> Page[Agent]:
        rows, total = self.repository.list_by_user(
            user_id, params.limit, params.offset
        )
        return Page(
            items=[Agent(**row) for row in rows],
            total=total,
            limit=params.limit,
            offset=params.offset,
        )

    def get_agent(self, agent_id: str, user_id: str) -> Agent:
        return Agent(**self.ensure_owned(agent_id, user_id))

    def update_agent(
        self, agent_id: str, user_id: str, payload: AgentUpdate
    ) -> Agent:
        existing = self.ensure_owned(agent_id, user_id)

        updates: dict = {}
        if payload.name is not None:
            updates["name"] = payload.name
        if payload.background_color is not None:
            updates["background_color"] = payload.background_color
        if payload.position is not None:
            updates["position"] = payload.position.value
        if payload.greeting is not None:
            updates["greeting"] = payload.greeting
        if payload.capability is not None:
            self._ensure_capability_allowed(user_id, payload.capability)
            updates["capability"] = payload.capability.value
        if payload.booking_enabled is not None:
            if payload.booking_enabled:
                self._ensure_feature_allowed(user_id, Feature.booking)
            updates["booking_enabled"] = payload.booking_enabled
        if payload.meeting_duration_minutes is not None:
            updates["meeting_duration_minutes"] = payload.meeting_duration_minutes

        if not updates:
            return Agent(**existing)

        updated = self.repository.update(agent_id, updates)
        return Agent(**updated)

    def ingest_document(
        self, agent_id: str, user_id: str, file: UploadFile
    ) -> IngestResponse:
        """Embed an uploaded document into an agent's knowledge base."""
        self.ensure_owned(agent_id, user_id)

        suffix = os.path.splitext(file.filename or "")[1]
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                shutil.copyfileobj(file.file, tmp)
                tmp_path = tmp.name

            # Imported lazily so agent CRUD works even without the RAG stack set up.
            from rag_bot.rag_engine import get_engine

            try:
                chunks = get_engine().ingest_file(
                    tmp_path, user_id=user_id, agent_id=agent_id
                )
            except ValueError as exc:  # unsupported file type
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
                )
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        return IngestResponse(chunks_indexed=chunks)
