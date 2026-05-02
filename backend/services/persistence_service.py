"""Persistence helpers for workflow state, checkpoints, MySQL, and memory."""

from __future__ import annotations

from typing import Any

from log import get_logger
from memory.service import get_memory_service
from storage.mysql_client import MySQLStore, get_mysql_pool
from storage.redis_client import RedisSessionStore
from workflow.state import CopilotState

logger = get_logger("api")


async def save_before_graph_checkpoint(
    store: RedisSessionStore,
    *,
    checkpoint_id: str,
    state: CopilotState,
) -> None:
    await store.save_checkpoint(
        checkpoint_id=f"{checkpoint_id}:before_graph",
        state=state.model_dump(),
        metadata={"stage": "before_graph", "context_window": state.context_window},
    )


async def save_after_graph_checkpoint(
    store: RedisSessionStore,
    *,
    checkpoint_id: str,
    final_state: CopilotState,
    llm_token_usage: list[dict[str, Any]],
) -> None:
    await store.save_checkpoint(
        checkpoint_id=f"{checkpoint_id}:after_graph",
        state=final_state.model_dump(),
        metadata={
            "stage": "after_graph",
            "llm_call_count": len(llm_token_usage),
            "total_tokens": sum(int(item.get("total_tokens") or 0) for item in llm_token_usage),
        },
    )


async def append_llm_token_usage_event(
    store: RedisSessionStore,
    *,
    session_id: str,
    checkpoint_id: str,
    llm_token_usage: list[dict[str, Any]],
    context_window: dict[str, Any],
) -> None:
    await store.append_event({
        "event_type": "llm_token_usage",
        "session_id": session_id,
        "checkpoint_id": checkpoint_id,
        "calls": llm_token_usage,
        "context_window": context_window,
    })


async def persist_to_mysql(state: CopilotState) -> None:
    """Persist key state projections to MySQL."""
    pool = await get_mysql_pool()
    db = MySQLStore(pool)
    await db.upsert_session(state.session_id)

    if state.job:
        await db.save_job(state.job.id, state.session_id, state.job.model_dump(), state.job.version)

    if state.candidate_profile:
        profile_id = f"profile_{state.session_id}"
        await db.save_candidate_profile(profile_id, state.session_id, state.candidate_profile.model_dump())

    if state.resume_content_json:
        content_id = f"content_{state.session_id}"
        await db.save_resume_content(
            content_id,
            state.session_id,
            state.resume_content_json.model_dump(),
            state.resume_content_json.meta.version,
            state.resume_content_json.meta.content_hash,
        )

    render_id = f"render_{state.session_id}"
    await db.save_render_config(
        render_id,
        state.session_id,
        state.render_config.model_dump(),
        state.render_config.version,
    )

    if state.resume_html.html:
        html_id = f"html_{state.session_id}"
        await db.save_resume_html(
            html_id,
            state.session_id,
            state.resume_html.html,
            state.resume_html.version,
            state.resume_html.derived_from_content_version,
            state.resume_html.derived_from_render_version,
            state.resume_html.checksum,
        )

    if state.interview_qa:
        interview_id = f"interview_{state.session_id}"
        await db.save_interview_qa(
            interview_id,
            state.session_id,
            {"interview_qa": [qa.model_dump() for qa in state.interview_qa]},
            len(state.interview_qa),
        )


async def persist_to_mysql_safe(state: CopilotState) -> None:
    try:
        await persist_to_mysql(state)
    except Exception as e:
        logger.error("MySQL persistence failed: %s", e, exc_info=True)


async def persist_to_memory_safe(
    old_state: CopilotState | None,
    final_state: CopilotState,
    user_message: str,
) -> None:
    try:
        memory_service = await get_memory_service()
        await memory_service.observe_and_write(
            old_state=old_state,
            final_state=final_state,
            user_message=user_message,
        )
    except Exception as e:
        logger.error("Memory persistence failed: %s", e, exc_info=True)


def add_background_persistence_tasks(
    background_tasks: Any,
    *,
    previous_state: CopilotState | None,
    final_state: CopilotState,
    user_message: str,
) -> None:
    background_tasks.add_task(persist_to_mysql_safe, final_state)
    background_tasks.add_task(persist_to_memory_safe, previous_state, final_state, user_message)

