"""Typed contracts for the memory subsystem."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MemoryScope(str, Enum):
    SESSION = "session"
    USER = "user"
    GLOBAL = "global"


class MemoryKind(str, Enum):
    PROFILE_FACT = "profile_fact"
    PREFERENCE = "preference"
    ARTIFACT = "artifact"
    EVENT = "event"
    SUMMARY = "summary"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MemoryRecord(BaseModel):
    """Canonical memory record stored in MySQL and indexed in ChromaDB."""

    model_config = ConfigDict(use_enum_values=True)

    memory_id: str
    user_id: str | None = None
    session_id: str | None = None
    scope: MemoryScope = MemoryScope.SESSION
    kind: MemoryKind = MemoryKind.PROFILE_FACT
    content: str
    data: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    status: MemoryStatus = MemoryStatus.ACTIVE
    content_hash: str = ""
    created_at: str = ""
    updated_at: str = ""
    expires_at: str | None = None


class MemoryQuery(BaseModel):
    """Recall request built by API/session layer before workflow execution."""

    user_id: str | None = None
    session_id: str | None = None
    query: str = ""
    kinds: list[MemoryKind | str] = Field(default_factory=list)
    top_k: int = 8
    use_vector: bool = True
    use_rerank: bool = True


class MemoryHit(BaseModel):
    """One recalled memory plus retrieval metadata."""

    model_config = ConfigDict(use_enum_values=True)

    record: MemoryRecord
    score: float = 0.0
    source: str = "mysql"
    reason: str = ""


class MemoryBundle(BaseModel):
    """All memory context attached to one workflow request."""

    hits: list[MemoryHit] = Field(default_factory=list)
    summary: str = ""


class MemoryEvent(BaseModel):
    """Append-only memory operation event."""

    event_id: str
    user_id: str | None = None
    session_id: str | None = None
    event_type: str
    memory_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
