"""Session state service backed by Redis."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from storage.redis_client import RedisSessionStore, get_redis_client
from workflow.state import CopilotState


RUNTIME_STATE_EXCLUDE = {
    "user_message",
    "user_attachments",
    "current_intent",
    "execution_plan",
    "reply_message",
    "agent_reply_message",
    "triggered_agents",
    "section_rationales",
    "memory_context",
    "retrieved_memories",
}


class SessionNotFoundError(Exception):
    """Raised when a requested session does not exist."""


@dataclass(frozen=True)
class SessionContext:
    session_id: str
    store: RedisSessionStore
    previous_state: CopilotState


def ensure_session_id(session_id: str | None = None) -> str:
    """Return the provided session id or create a new one."""
    return session_id or f"sess_{uuid.uuid4().hex[:16]}"


async def get_session_store(session_id: str) -> RedisSessionStore:
    client = await get_redis_client()
    return RedisSessionStore(session_id, client)


async def load_raw_state(store: RedisSessionStore) -> dict[str, Any] | None:
    return await store.load_state()


async def save_raw_state(store: RedisSessionStore, state: dict[str, Any]) -> None:
    await store.save_state(state)


async def load_or_create_session(session_id: str | None = None) -> SessionContext:
    resolved_session_id = ensure_session_id(session_id)
    store = await get_session_store(resolved_session_id)
    saved_state = await load_raw_state(store)
    previous_state = (
        CopilotState.model_validate(saved_state)
        if saved_state
        else CopilotState(session_id=resolved_session_id)
    )
    return SessionContext(
        session_id=resolved_session_id,
        store=store,
        previous_state=previous_state,
    )


async def load_existing_session(session_id: str) -> SessionContext:
    store = await get_session_store(session_id)
    saved_state = await load_raw_state(store)
    if not saved_state:
        raise SessionNotFoundError("会话不存在")
    return SessionContext(
        session_id=session_id,
        store=store,
        previous_state=CopilotState.model_validate(saved_state),
    )


async def load_existing_state(session_id: str) -> CopilotState:
    return (await load_existing_session(session_id)).previous_state


def dump_persistent_state(state: CopilotState) -> dict[str, Any]:
    return state.model_dump(exclude=RUNTIME_STATE_EXCLUDE)


async def save_persistent_state(store: RedisSessionStore, state: CopilotState) -> None:
    await save_raw_state(store, dump_persistent_state(state))

