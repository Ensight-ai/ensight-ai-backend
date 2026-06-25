"""Request/response models for chatting/talking with an agent."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    # History is kept server-side per conversation, so the widget only sends
    # the new question.
    question: str = Field(min_length=1)


class ChatResponse(BaseModel):
    answer: str
    language: str | None = None  # detected conversation language (ISO code)


class VoiceResponse(BaseModel):
    transcript: str  # what the visitor said (from speech-to-text)
    answer: str  # the agent's text answer
    audio_base64: str  # the spoken answer (MP3), base64-encoded
    audio_mime: str = "audio/mpeg"
    language: str | None = None  # conversation language used (ISO code)
