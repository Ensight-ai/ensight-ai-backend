"""Agent session business logic: public key -> conversation + session token."""

from fastapi import HTTPException, status

from app.agents.repository import AgentRepository
from app.conversations.repository import ConversationRepository
from app.core.security import create_session_token, generate_visitor_id
from app.sessions.schemas import SessionRequest, SessionResponse


class SessionService:
    def __init__(
        self,
        agents: AgentRepository,
        conversations: ConversationRepository,
    ) -> None:
        self.agents = agents
        self.conversations = conversations

    def create_session(self, payload: SessionRequest) -> SessionResponse:
        agent = self.agents.get_by_public_key(payload.public_key)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown agent key"
            )

        visitor_id = payload.visitor_id or generate_visitor_id()
        channel = "voice" if agent["capability"] == "voice" else "chat"

        conversation = self.conversations.create(
            agent_id=agent["id"],
            user_id=agent["user_id"],
            visitor_id=visitor_id,
            channel=channel,
        )

        token, expires_in = create_session_token(
            user_id=agent["user_id"],
            agent_id=agent["id"],
            capability=agent["capability"],
            visitor_id=visitor_id,
            conversation_id=conversation["id"],
        )
        return SessionResponse(
            access_token=token,
            expires_in=expires_in,
            agent_id=agent["id"],
            capability=agent["capability"],
            visitor_id=visitor_id,
            conversation_id=conversation["id"],
        )
