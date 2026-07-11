"""Chat turn business logic: history + language + RAG engine + logging.

When the agent has booking enabled (and the owner connected Google), the turn
runs through the engine's tool-calling path so the agent can collect details
and book a meeting; otherwise it uses the plain RAG answer path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator

from starlette.concurrency import run_in_threadpool

from app.chat.schemas import ChatRequest, ChatResponse
from app.conversations.message_repository import MessageRepository
from app.conversations.repository import ConversationRepository
from app.core.language import detect_language, language_name
from app.sessions.schemas import AgentSession

if TYPE_CHECKING:  # avoid importing the heavy RAG stack at startup
    from app.agents.repository import AgentRepository
    from app.booking.service import BookingService
    from rag_bot.rag_engine import RagEngine


class ChatService:
    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        engine: "RagEngine",
        agents: "AgentRepository | None" = None,
        booking_service: "BookingService | None" = None,
    ) -> None:
        self.conversations = conversations
        self.messages = messages
        self.engine = engine
        # Optional: only needed for the booking-enabled path.
        self.agents = agents
        self.booking_service = booking_service

    def chat(self, session: AgentSession, payload: ChatRequest) -> ChatResponse:
        history = self.messages.history(session.conversation_id)
        language_code = self._session_language(session, payload.question)

        answer = self._answer(
            session,
            payload.question,
            history,
            language_name(language_code),
        )

        self._record_turn(session, payload.question, answer)
        return ChatResponse(answer=answer, language=language_code)

    async def astream(
        self, session: AgentSession, payload: ChatRequest
    ) -> AsyncIterator[dict]:
        """Stream a chat turn as events for the WebSocket route.

        Token-streams the plain answer path. The booking path can't stream
        (it runs a tool-calling loop), so it computes the full answer off the
        event loop and emits it as a single token.
        """
        history = await run_in_threadpool(
            self.messages.history, session.conversation_id
        )
        language_code = await run_in_threadpool(
            self._session_language, session, payload.question
        )
        language = language_name(language_code)

        tools = self._booking_tools(session)
        if tools:
            answer = await run_in_threadpool(
                self.engine.chat_with_tools,
                payload.question,
                user_id=session.user_id,
                agent_id=session.agent_id,
                tools=tools,
                chat_history=history,
                language=language,
            )
            yield {"type": "token", "data": answer}
        else:
            parts: list[str] = []
            async for token in self.engine.astream_chat(
                payload.question,
                user_id=session.user_id,
                agent_id=session.agent_id,
                chat_history=history,
                language=language,
            ):
                parts.append(token)
                yield {"type": "token", "data": token}
            answer = "".join(parts)

        await run_in_threadpool(
            self._record_turn, session, payload.question, answer
        )
        yield {"type": "done", "language": language_code}

    # --- helpers ----------------------------------------------------------
    def _answer(
        self,
        session: AgentSession,
        question: str,
        history,
        language: str | None,
    ) -> str:
        tools = self._booking_tools(session)
        if tools:
            return self.engine.chat_with_tools(
                question,
                user_id=session.user_id,
                agent_id=session.agent_id,
                tools=tools,
                chat_history=history,
                language=language,
            )
        return self.engine.chat(
            question,
            user_id=session.user_id,
            agent_id=session.agent_id,
            chat_history=history,
            language=language,
        )

    def _booking_tools(self, session: AgentSession) -> list | None:
        """Build booking tools if this agent has booking turned on."""
        if not (self.agents and self.booking_service):
            return None
        agent = self.agents.get_owned(session.agent_id, session.user_id)
        if not agent or not agent.get("booking_enabled"):
            return None

        from app.chat.booking_tools import build_booking_tools

        return build_booking_tools(
            self.booking_service,
            user_id=session.user_id,
            agent_id=session.agent_id,
            conversation_id=session.conversation_id,
            duration_minutes=agent.get("meeting_duration_minutes"),
        )

    def _session_language(
        self, session: AgentSession, question: str
    ) -> str | None:
        """Determine (and persist once) the conversation language."""
        language_code = self.conversations.get_language(session.conversation_id)
        if not language_code:
            language_code = detect_language(question)
            if language_code:
                self.conversations.set_language(
                    session.conversation_id, language_code
                )
        return language_code

    def _record_turn(
        self, session: AgentSession, question: str, answer: str
    ) -> None:
        # Both messages in a single insert — one DB round trip instead of two.
        self.messages.add_turn(
            conversation_id=session.conversation_id,
            agent_id=session.agent_id,
            question=question,
            answer=answer,
        )
        self.conversations.touch(session.conversation_id)
