"""Application orchestration for chat and render workflows."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

from log import get_logger
from memory.context_window import MemoryContextWindowManager
from memory.contracts import MemoryBundle
from memory.service import get_memory_service
from models.llm import begin_llm_trace, end_llm_trace, get_llm_trace_records
from services import persistence_service, session_service
from workflow.graph import compile_graph
from workflow.state import CopilotState

logger = get_logger("api")

_graph: Any | None = None


class ContextWindowExceededError(Exception):
    """Raised when graph input cannot fit inside the configured context window."""


class WorkflowExecutionError(Exception):
    """Raised when workflow graph execution fails."""


@dataclass(frozen=True)
class WorkflowRunResult:
    session_id: str
    previous_state: CopilotState
    final_state: CopilotState
    user_message: str


def get_workflow_graph() -> Any:
    global _graph
    if _graph is None:
        _graph = compile_graph()
    return _graph


async def invoke_workflow_graph(
    graph: Any,
    payload: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> Any:
    if hasattr(graph, "ainvoke"):
        return await graph.ainvoke(payload, config=config)
    return await asyncio.to_thread(graph.invoke, payload, config)


async def run_chat(
    *,
    session_id: str | None,
    user_message: str,
    user_attachments: list[dict[str, Any]],
) -> WorkflowRunResult:
    session = await session_service.load_or_create_session(session_id)
    logger.info("Chat request: session=%s, msg_len=%d", session.session_id, len(user_message))

    previous_state = session.previous_state
    state = previous_state.model_copy(deep=True)

    state.user_message = user_message
    state.user_attachments = user_attachments

    state = await _inject_memory_context(
        session_id=session.session_id,
        state=state,
        previous_state=previous_state,
        user_message=user_message,
    )

    graph = get_workflow_graph()
    checkpoint_id = f"ckpt_{uuid.uuid4().hex[:12]}"
    await persistence_service.save_before_graph_checkpoint(
        session.store,
        checkpoint_id=checkpoint_id,
        state=state,
    )

    trace_tokens = begin_llm_trace(session.session_id)
    try:
        result = await invoke_workflow_graph(
            graph,
            state.model_dump(),
            config={"run_name": f"API-Chat-Request: {session.session_id}"},
        )
    except Exception as e:
        logger.error("Workflow execution failed: %s", e, exc_info=True)
        raise WorkflowExecutionError(str(e)) from e
    finally:
        llm_token_usage = get_llm_trace_records()
        end_llm_trace(trace_tokens)

    final_state = CopilotState.model_validate(result)
    final_state.context_window = state.context_window
    final_state.llm_token_usage = llm_token_usage

    await persistence_service.append_llm_token_usage_event(
        session.store,
        session_id=session.session_id,
        checkpoint_id=checkpoint_id,
        llm_token_usage=llm_token_usage,
        context_window=final_state.context_window,
    )
    await persistence_service.save_after_graph_checkpoint(
        session.store,
        checkpoint_id=checkpoint_id,
        final_state=final_state,
        llm_token_usage=llm_token_usage,
    )
    await session_service.save_persistent_state(session.store, final_state)

    return WorkflowRunResult(
        session_id=session.session_id,
        previous_state=previous_state,
        final_state=final_state,
        user_message=user_message,
    )


async def render_resume(
    *,
    session_id: str,
    render_instruction: str,
) -> WorkflowRunResult:
    session = await session_service.load_existing_session(session_id)
    previous_state = session.previous_state
    state = previous_state.model_copy(deep=True)
    state.user_message = render_instruction
    state.current_intent = "render_edit"
    state.execution_plan = ["render_agent"]

    graph = get_workflow_graph()
    try:
        result = await invoke_workflow_graph(graph, state.model_dump())
    except Exception as e:
        logger.error("Render failed: %s", e, exc_info=True)
        raise WorkflowExecutionError(str(e)) from e

    final_state = CopilotState.model_validate(result)
    await session_service.save_persistent_state(session.store, final_state)

    return WorkflowRunResult(
        session_id=session_id,
        previous_state=previous_state,
        final_state=final_state,
        user_message=render_instruction,
    )


async def _inject_memory_context(
    *,
    session_id: str,
    state: CopilotState,
    previous_state: CopilotState,
    user_message: str,
) -> CopilotState:
    try:
        memory_service = await get_memory_service()
        memory_bundle = await memory_service.recall(
            session_id=session_id,
            message=user_message,
            state=previous_state,
        )
        state.memory_context = memory_service.format_context(memory_bundle)
        state.retrieved_memories = [hit.model_dump() for hit in memory_bundle.hits]
        managed_context = MemoryContextWindowManager().manage(state, memory_bundle)
        state = managed_context.state
        state.context_window = managed_context.stats.model_dump()
        if not managed_context.stats.within_budget:
            raise ContextWindowExceededError(
                "上下文超过 128K Token 窗口，动态摘要与裁剪后仍无法安全执行 LLM 调用。"
            )
    except ContextWindowExceededError:
        raise
    except Exception as e:
        logger.warning("Memory recall skipped: %s", e)
        managed_context = MemoryContextWindowManager().manage(state, MemoryBundle())
        state = managed_context.state
        state.context_window = managed_context.stats.model_dump()
        if not managed_context.stats.within_budget:
            raise ContextWindowExceededError(
                "上下文超过 128K Token 窗口，裁剪后仍无法安全执行 LLM 调用。"
            ) from e
    return state
