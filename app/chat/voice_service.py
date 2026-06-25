"""Voice turn business logic: STT -> RAG -> TTS + logging."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, AsyncIterator

from fastapi import HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.chat.schemas import VoiceResponse
from app.conversations.message_repository import MessageRepository
from app.conversations.repository import ConversationRepository
from app.core.language import (
    STT_CANDIDATE_LOCALES,
    code_from_locale,
    language_name,
    to_locale,
)
from app.sessions.schemas import AgentSession

# Synthesize speech once a buffered sentence is at least this long, so we emit
# audio mid-answer (lower latency) without chopping into tiny clips.
_MIN_TTS_CHARS = 20
_SENTENCE_ENDINGS = (".", "!", "?", "\n")

if TYPE_CHECKING:  # avoid importing the heavy stacks at startup
    from rag_bot.rag_engine import RagEngine
    from rag_bot.voice_engine import VoiceEngine


class VoiceService:
    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        engine: VoiceEngine,
        rag_engine: RagEngine,
    ) -> None:
        self.conversations = conversations
        self.messages = messages
        self.engine = engine
        # Used directly for streaming the answer text in the realtime path.
        self.rag_engine = rag_engine

    def voice(
        self,
        session: AgentSession,
        *,
        audio_bytes: bytes,
        encoding: str,
        sample_rate_hertz: int | None,
    ) -> VoiceResponse:
        history = self.messages.history(session.conversation_id)

        # If the session already has a language, transcribe/speak in it;
        # otherwise let Google auto-detect from a candidate set.
        language_code = self.conversations.get_language(session.conversation_id)
        known_locale = to_locale(language_code) if language_code else None

        try:
            result = self.engine.respond(
                audio_bytes,
                user_id=session.user_id,
                agent_id=session.agent_id,
                chat_history=history,
                encoding=encoding,
                sample_rate_hertz=sample_rate_hertz,
                language_code=known_locale,
                alternative_language_codes=(
                    None if known_locale else STT_CANDIDATE_LOCALES
                ),
            )
        except ValueError as exc:  # unsupported encoding
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            )

        if not result.transcript:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not transcribe any speech from the audio.",
            )

        # Persist the detected language for the rest of the session.
        if not language_code and result.language:
            language_code = code_from_locale(result.language)
            if language_code:
                self.conversations.set_language(
                    session.conversation_id, language_code
                )

        self.messages.add(
            conversation_id=session.conversation_id,
            agent_id=session.agent_id,
            role="user",
            content=result.transcript,
        )
        self.messages.add(
            conversation_id=session.conversation_id,
            agent_id=session.agent_id,
            role="assistant",
            content=result.answer,
        )
        self.conversations.touch(session.conversation_id)

        return VoiceResponse(
            transcript=result.transcript,
            answer=result.answer,
            audio_base64=base64.b64encode(result.audio).decode("ascii"),
            language=language_code,
        )

    async def astream(
        self,
        session: AgentSession,
        *,
        audio_bytes: bytes,
        encoding: str,
        sample_rate_hertz: int | None,
    ) -> AsyncIterator[dict]:
        """Stream a voice turn for the WebSocket route.

        Yields, in order:
          * ``{"type": "transcript", "text": ...}``
          * ``{"type": "token", "data": ...}`` for each answer delta
          * ``{"type": "audio", "data": <mp3 bytes>}`` per spoken sentence
          * ``{"type": "done", "language": ...}``
        Audio is synthesized sentence-by-sentence so playback can start before
        the full answer finishes.
        """
        language_code = await run_in_threadpool(
            self.conversations.get_language, session.conversation_id
        )
        known_locale = to_locale(language_code) if language_code else None

        transcript, detected_locale = await run_in_threadpool(
            self.engine.transcribe,
            audio_bytes,
            encoding=encoding,
            sample_rate_hertz=sample_rate_hertz,
            language_code=known_locale,
            alternative_language_codes=(
                None if known_locale else STT_CANDIDATE_LOCALES
            ),
        )
        if not transcript:
            yield {"type": "error", "detail": "Could not transcribe audio."}
            return

        effective_locale = (
            known_locale or detected_locale or self.engine.language_code
        )
        if not language_code:
            language_code = code_from_locale(effective_locale)
            if language_code:
                await run_in_threadpool(
                    self.conversations.set_language,
                    session.conversation_id,
                    language_code,
                )

        yield {"type": "transcript", "text": transcript}

        history = await run_in_threadpool(
            self.messages.history, session.conversation_id
        )
        spoken_language = language_name(code_from_locale(effective_locale))

        parts: list[str] = []
        sentence = ""
        async for token in self.rag_engine.astream_chat(
            transcript,
            user_id=session.user_id,
            agent_id=session.agent_id,
            chat_history=history,
            language=spoken_language,
        ):
            parts.append(token)
            sentence += token
            yield {"type": "token", "data": token}

            if (
                len(sentence) >= _MIN_TTS_CHARS
                and any(end in sentence for end in _SENTENCE_ENDINGS)
            ):
                audio = await run_in_threadpool(
                    self.engine.synthesize, sentence, language_code=effective_locale
                )
                yield {"type": "audio", "data": audio}
                sentence = ""

        if sentence.strip():
            audio = await run_in_threadpool(
                self.engine.synthesize, sentence, language_code=effective_locale
            )
            yield {"type": "audio", "data": audio}

        answer = "".join(parts)
        await run_in_threadpool(
            self.messages.add,
            conversation_id=session.conversation_id,
            agent_id=session.agent_id,
            role="user",
            content=transcript,
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
