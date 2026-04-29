"""Memory IDs, hashing, retention, and indexing policy."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from memory.contracts import MemoryKind


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def content_hash(content: str) -> str:
    return stable_hash((content or "").strip())


def owner_key(user_id: str | None, session_id: str | None) -> str:
    if user_id:
        return f"user:{user_id}"
    if session_id:
        return f"session:{session_id}"
    return "global"


def build_memory_id(
    *,
    kind: str | MemoryKind,
    source_id: str,
    user_id: str | None = None,
    session_id: str | None = None,
) -> str:
    kind_value = kind.value if isinstance(kind, MemoryKind) else str(kind)
    raw = "|".join([owner_key(user_id, session_id), kind_value, source_id])
    return f"mem_{stable_hash(raw)[:24]}"


def should_index_kind(kind: str | MemoryKind) -> bool:
    kind_value = kind.value if isinstance(kind, MemoryKind) else str(kind)
    return kind_value in {
        MemoryKind.PROFILE_FACT.value,
        MemoryKind.PREFERENCE.value,
        MemoryKind.ARTIFACT.value,
        MemoryKind.SUMMARY.value,
    }


def compact_text(text: str, max_chars: int = 4000) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars].rstrip() + "..."
