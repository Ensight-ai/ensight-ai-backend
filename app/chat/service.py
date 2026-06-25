"""Chat turn business logic: history + language + RAG engine + logging."""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator

from starlette.concurrency import run_in_threadpool

from app.chat.schemas import ChatRequest, ChatResponse
from app.conversations.message_repository import MessageRepository
from app.conversations.repository import ConversationRepository
from app.core.language import detect_language, language_name
from app.sessions.schemas import AgentSession

if TYPE_CHECKING:  # avoid importing the heavy RAG stack at startup
    from rag_bot.rag_engine import RagEngine


class ChatService:
    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        engine: RagEngine,
    ) -> None:
        self.conversations = conversations
        self.messages = messages
        self.engine = engine

    def chat(self, session: AgentSession, payload: ChatRequest) -> ChatResponse:
        history = self.messages.history(session.conversation_id)

        # Determine the session language once, then reuse it for every turn.
        language_code = self.conversations.get_language(session.conversation_id)
        if not language_code:
            language_code = detect_language(payload.question)
            if language_code:
                self.conversations.set_language(
                    session.conversation_id, language_code
                )

        answer = self.engine.chat(
            payload.question,
            user_id=session.user_id,
            agent_id=session.agent_id,
            chat_history=history,
            language=language_name(language_code),
        )

        self.messages.add(
            conversation_id=session.conversation_id,
            agent_id=session.agent_id,
            role="user",
            content=payload.question,
        )
        self.messages.add(
            conversation_id=session.conversation_id,
            agent_id=session.agent_id,
            role="assistant",
            content=answer,
        )
        self.conversations.touch(session.conversation_id)

        return ChatResponse(answer=answer, language=language_code)

    async def astream(
        self, session: AgentSession, payload: ChatRequest
    ) -> AsyncIterator[dict]:
        """Stream a chat turn as events for the WebSocket route.

        Yields ``{"type": "token", "data": ...}`` for each delta, then a final
        ``{"type": "done", "language": ...}``. DB calls run in a threadpool so
        they don't block the event loop.
        """
        history = await run_in_threadpool(
            self.messages.history, session.conversation_id
        )

        language_code = await run_in_threadpool(
            self.conversations.get_language, session.conversation_id
        )
        if not language_code:
            language_code = detect_language(payload.question)
            if language_code:
                await run_in_threadpool(
                    self.conversations.set_language,
                    session.conversation_id,
                    language_code,
                )

        parts: list[str] = []
        async for token in self.engine.astream_chat(
            payload.question,
            user_id=session.user_id,
            agent_id=session.agent_id,
            chat_history=history,
            language=language_name(language_code),
        ):
            parts.append(token)
            yield {"type": "token", "data": token}

        answer = "".join(parts)
        await run_in_threadpool(
            self.messages.add,
            conversation_id=session.conversation_id,
            agent_id=session.agent_id,
            role="user",
            content=payload.question,
        )
        await run_in_threadpool(
            self.messages.add,
            conversation_id=session.conversation_id,
            agent_id=session.agent_id,
            role="assistant",
            content=answer,
        )
        await run_in_threadpool(
            self.conversations.touch, session.conversation_id
        )

        yield {"type": "done", "language": language_code}
