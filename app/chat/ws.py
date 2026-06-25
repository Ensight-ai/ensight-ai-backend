"""Realtime WebSocket routes for immediate chat + voice.

Auth: the widget connects with the session token in the query string
(``/ws/chat?token=...``), since browser WebSockets can't send headers. The
token is the same one issued by ``POST /sessions``.

Protocols
---------
``/ws/chat``  (text frames)
  client -> ``{"question": "..."}``
  server -> ``{"type":"token","data":"..."}`` * N, then ``{"type":"done","language":"es"}``

``/ws/voice`` (binary audio in, mixed frames out)
  client -> binary audio chunks, then text ``{"type":"end"}`` to finish an utterance
  server -> ``{"type":"transcript","text":...}``,
            ``{"type":"token","data":...}`` * N,
            binary MP3 frames (one per spoken sentence),
            ``{"type":"done","language":...}``
"""

import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status

from app.agents.schemas import Capability
from app.chat.dependencies import get_chat_service, get_voice_service
from app.chat.schemas import ChatRequest
from app.chat.service import ChatService
from app.chat.voice_service import VoiceService
from app.core.security import decode_session_token
from app.sessions.schemas import AgentSession

ws_router = APIRouter(tags=["realtime"])


def _session_from_token(token: str | None) -> AgentSession | None:
    if not token:
        return None
    try:
        payload = decode_session_token(token)
    except Exception:
        return None
    return AgentSession(
        user_id=payload["user_id"],
        agent_id=payload["agent_id"],
        capability=payload["capability"],
        visitor_id=payload["visitor_id"],
        conversation_id=payload["conversation_id"],
    )


async def _authenticate(
    websocket: WebSocket, *, allowed: tuple[Capability, ...]
) -> AgentSession | None:
    """Validate the session token + capability, or close the socket."""
    session = _session_from_token(websocket.query_params.get("token"))
    if session is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    if session.capability not in allowed:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Agent capability not allowed",
        )
        return None
    return session


@ws_router.websocket("/ws/chat")
async def ws_chat(
    websocket: WebSocket,
    service: ChatService = Depends(get_chat_service),
):
    session = await _authenticate(
        websocket, allowed=(Capability.chat, Capability.both)
    )
    if session is None:
        return

    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            question = (data or {}).get("question", "").strip()
            if not question:
                await websocket.send_json(
                    {"type": "error", "detail": "Empty question"}
                )
                continue
            async for event in service.astream(
                session, ChatRequest(question=question)
            ):
                await websocket.send_json(event)
    except WebSocketDisconnect:
        return


@ws_router.websocket("/ws/voice")
async def ws_voice(
    websocket: WebSocket,
    service: VoiceService = Depends(get_voice_service),
):
    session = await _authenticate(
        websocket, allowed=(Capability.voice, Capability.both)
    )
    if session is None:
        return

    await websocket.accept()
    encoding = websocket.query_params.get("encoding", "WEBM_OPUS")
    rate = websocket.query_params.get("sample_rate")
    sample_rate_hertz = int(rate) if rate else None

    buffer = bytearray()
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            chunk = message.get("bytes")
            if chunk is not None:
                buffer.extend(chunk)
                continue

            text = message.get("text")
            if text is None:
                continue
            try:
                control = json.loads(text)
            except json.JSONDecodeError:
                continue

            action = control.get("type")
            if action == "reset":
                buffer.clear()
            elif action == "end":
                audio_bytes = bytes(buffer)
                buffer.clear()
                if not audio_bytes:
                    await websocket.send_json(
                        {"type": "error", "detail": "No audio received"}
                    )
                    continue
                async for event in service.astream(
                    session,
                    audio_bytes=audio_bytes,
                    encoding=encoding,
                    sample_rate_hertz=sample_rate_hertz,
                ):
                    if event["type"] == "audio":
                        await websocket.send_bytes(event["data"])
                    else:
                        await websocket.send_json(event)
    except WebSocketDisconnect:
        return
