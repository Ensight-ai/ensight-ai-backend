"""Widget-facing conversation routes (chat + voice).

Authenticated with an agent *session* token (issued by ``POST /sessions``).
Chat and voice use separate controllers so a /chat request never builds the
voice engine (and vice versa).
"""

from fastapi import APIRouter, Depends, Form, UploadFile

from app.chat.dependencies import get_chat_service, get_voice_service
from app.chat.schemas import ChatRequest, ChatResponse, VoiceResponse
from app.chat.service import ChatService
from app.chat.voice_service import VoiceService
from app.dependencies import require_chat, require_voice
from app.sessions.schemas import AgentSession


class ChatController:
    def __init__(self, service: ChatService = Depends(get_chat_service)) -> None:
        self.service = service

    def chat(self, session: AgentSession, payload: ChatRequest) -> ChatResponse:
        return self.service.chat(session, payload)


class VoiceController:
    def __init__(
        self, service: VoiceService = Depends(get_voice_service)
    ) -> None:
        self.service = service

    def voice(
        self,
        session: AgentSession,
        *,
        audio_bytes: bytes,
        encoding: str,
        sample_rate_hertz: int | None,
    ) -> VoiceResponse:
        return self.service.voice(
            session,
            audio_bytes=audio_bytes,
            encoding=encoding,
            sample_rate_hertz=sample_rate_hertz,
        )


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    session: AgentSession = Depends(require_chat),
    controller: ChatController = Depends(),
):
    return controller.chat(session, payload)


@router.post("/voice", response_model=VoiceResponse)
def voice(
    file: UploadFile,
    encoding: str = Form("WEBM_OPUS"),
    sample_rate_hertz: int | None = Form(None),
    session: AgentSession = Depends(require_voice),
    controller: VoiceController = Depends(),
):
    audio_bytes = file.file.read()
    return controller.voice(
        session,
        audio_bytes=audio_bytes,
        encoding=encoding,
        sample_rate_hertz=sample_rate_hertz,
    )
