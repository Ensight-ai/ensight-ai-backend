"""Request/response models for agents."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# Hex color like #fff or #2563eb.
_HEX_COLOR = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"


class Capability(str, Enum):
    """What an agent can do. Gated by the owner's plan."""

    chat = "chat"
    voice = "voice"
    both = "both"


class Position(str, Enum):
    """Where the widget sits on the page."""

    bottom_left = "bottom-left"
    bottom_right = "bottom-right"


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    capability: Capability = Capability.chat
    background_color: str = Field(default="#2563eb", pattern=_HEX_COLOR)
    position: Position = Position.bottom_right


class AgentUpdate(BaseModel):
    """All fields optional — only provided ones are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    capability: Capability | None = None
    background_color: str | None = Field(default=None, pattern=_HEX_COLOR)
    position: Position | None = None


class Agent(BaseModel):
    id: str
    user_id: str
    name: str
    capability: Capability
    background_color: str
    position: Position
    # Non-secret key the website widget uses to start a session.
    public_key: str
    created_at: datetime | None = None


class IngestResponse(BaseModel):
    chunks_indexed: int
