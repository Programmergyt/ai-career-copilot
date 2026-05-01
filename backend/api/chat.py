"""POST /api/chat — 主对话接口。"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from api.chat_input import prepare_chat_input
from workflow.graph import compile_graph
from workflow.state import CopilotState
from memory.context_window import MemoryContextWindowManager
from memory.contracts import MemoryBundle
from memory.service import get_memory_service
from models.llm import begin_llm_trace, end_llm_trace, get_llm_trace_records
from storage.redis_client import get_redis_client, RedisSessionStore
from storage.mysql_client import get_mysql_pool, MySQLStore
from log import get_logger

logger = get_logger("api")

router = APIRouter(prefix="/api", tags=["chat"])

_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = compile_graph()
    return _graph


async def _aload_state(store: RedisSessionStore) -> dict[str, Any] | None:
    return await store.load_state()


async def _asave_state(store: RedisSessionStore, state: dict[str, Any]) -> None:
    await store.save_state(state)


async def _ainvoke_graph(graph: Any, payload: dict[str, Any], *, config: dict[str, Any] | None = None) -> Any:
    if hasattr(graph, "ainvoke"):
        return await graph.ainvoke(payload, config=config)
    return await asyncio.to_thread(graph.invoke, payload, config)


class ChatRequest(BaseModel):
    session_id: str = ""
    message: str
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    session_id: str
    reply_message: str = ""
    job: dict | None = None
    gaps: list[dict] = Field(default_factory=list)
    questions_to_ask: list[dict] = Field(default_factory=list)
    resume_content_json: dict | None = None
    render_config: dict | None = None
    resume_html: dict | None = None
    interview_qa: list[dict] = Field(default_factory=list)
    triggered_agents: list[str] = Field(default_factory=list)
    llm_token_usage: list[dict] = Field(default_factory=list)
    context_window: dict = Field(default_factory=dict)


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, background_tasks: BackgroundTasks) -> ChatResponse:
    """主对话接口。"""
    session_id = req.session_id or f"sess_{uuid.uuid4().hex[:16]}"
    logger.info("Chat request: session=%s, msg_len=%d", session_id, len(req.message))

    # 从 Redis 加载或创建状态
    redis_client = await get_redis_client()
    store = RedisSessionStore(session_id, redis_client)
    saved_state = await _aload_state(store)

    if saved_state:
        previous_state = CopilotState.model_validate(saved_state)
    else:
        previous_state = CopilotState(session_id=session_id)
    state = previous_state.model_copy(deep=True)

    # 注入用户输入
    prepared_input = prepare_chat_input(req.message, req.attachments)
    state.user_message = prepared_input.user_message
    state.user_attachments = prepared_input.user_attachments

    # 记忆模块在 workflow 外部执行检索，并只向 state 注入运行时上下文。
    try:
        memory_service = await get_memory_service()
        memory_bundle = await memory_service.recall(
            session_id=session_id,
            message=prepared_input.user_message,
            state=previous_state,
        )
        state.memory_context = memory_service.format_context(memory_bundle)
        state.retrieved_memories = [hit.model_dump() for hit in memory_bundle.hits]
        managed_context = MemoryContextWindowManager().manage(state, memory_bundle)
        state = managed_context.state
        state.context_window = managed_context.stats.model_dump()
        if not managed_context.stats.within_budget:
            raise HTTPException(
                status_code=413,
                detail="上下文超过 128K Token 窗口，动态摘要与裁剪后仍无法安全执行 LLM 调用。",
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.warning("Memory recall skipped: %s", e)
        managed_context = MemoryContextWindowManager().manage(state, MemoryBundle())
        state = managed_context.state
        state.context_window = managed_context.stats.model_dump()
        if not managed_context.stats.within_budget:
            raise HTTPException(
                status_code=413,
                detail="上下文超过 128K Token 窗口，裁剪后仍无法安全执行 LLM 调用。",
            )

    # 执行 workflow graph，加上config指定langsmith的run_name，方便在LangSmith上查看每次API调用的执行详情
    graph = _get_graph()
    checkpoint_id = f"ckpt_{uuid.uuid4().hex[:12]}"
    await store.save_checkpoint(
        checkpoint_id=f"{checkpoint_id}:before_graph",
        state=state.model_dump(),
        metadata={"stage": "before_graph", "context_window": state.context_window},
    )
    trace_tokens = begin_llm_trace(session_id)
    try:
        result = await _ainvoke_graph(graph, state.model_dump(), config={"run_name": f"API-Chat-Request: {session_id}"})
    except Exception as e:
        logger.error("Workflow execution failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理失败: {e}")
    finally:
        llm_token_usage = get_llm_trace_records()
        end_llm_trace(trace_tokens)

    # 构建响应状态
    final_state = CopilotState.model_validate(result)
    final_state.context_window = state.context_window
    final_state.llm_token_usage = llm_token_usage
    await store.append_event({
        "event_type": "llm_token_usage",
        "session_id": session_id,
        "checkpoint_id": checkpoint_id,
        "calls": llm_token_usage,
        "context_window": final_state.context_window,
    })
    await store.save_checkpoint(
        checkpoint_id=f"{checkpoint_id}:after_graph",
        state=final_state.model_dump(),
        metadata={
            "stage": "after_graph",
            "llm_call_count": len(llm_token_usage),
            "total_tokens": sum(int(item.get("total_tokens") or 0) for item in llm_token_usage),
        },
    )

    # 持久化到 Redis
    persist_data = final_state.model_dump(exclude={"user_message", "user_attachments", "current_intent",
                                                     "execution_plan", "reply_message", "agent_reply_message",
                                                     "triggered_agents", "section_rationales", "memory_context",
                                                     "retrieved_memories"})
    await _asave_state(store, persist_data)

    # 后台持久化到 MySQL，避免同步阻塞请求主链。
    background_tasks.add_task(_persist_to_mysql_safe, final_state)
    background_tasks.add_task(
        _persist_to_memory_safe,
        previous_state,
        final_state,
        prepared_input.user_message,
    )

    return ChatResponse(
        session_id=session_id,
        reply_message=final_state.reply_message,
        job=final_state.job.model_dump() if final_state.job else None,
        gaps=[g.model_dump() for g in final_state.gaps],
        questions_to_ask=[q.model_dump() for q in final_state.questions_to_ask],
        resume_content_json=final_state.resume_content_json.model_dump() if final_state.resume_content_json else None,
        render_config=final_state.render_config.model_dump(),
        resume_html=final_state.resume_html.model_dump(),
        interview_qa=[qa.model_dump() for qa in final_state.interview_qa],
        triggered_agents=final_state.triggered_agents,
        llm_token_usage=final_state.llm_token_usage,
        context_window=final_state.context_window,
    )


async def _persist_to_mysql(state: CopilotState) -> None:
    """将关键状态异步持久化到 MySQL。"""
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
            content_id, state.session_id,
            state.resume_content_json.model_dump(),
            state.resume_content_json.meta.version,
            state.resume_content_json.meta.content_hash,
        )

    render_id = f"render_{state.session_id}"
    await db.save_render_config(render_id, state.session_id,
                                state.render_config.model_dump(), state.render_config.version)

    if state.resume_html.html:
        html_id = f"html_{state.session_id}"
        await db.save_resume_html(
            html_id, state.session_id, state.resume_html.html,
            state.resume_html.version,
            state.resume_html.derived_from_content_version,
            state.resume_html.derived_from_render_version,
            state.resume_html.checksum,
        )

    if state.interview_qa:
        interview_id = f"interview_{state.session_id}"
        await db.save_interview_qa(
            interview_id, state.session_id,
            {"interview_qa": [qa.model_dump() for qa in state.interview_qa]},
            len(state.interview_qa),
        )


async def _persist_to_mysql_safe(state: CopilotState) -> None:
    try:
        await _persist_to_mysql(state)
    except Exception as e:
        logger.error("MySQL persistence failed: %s", e, exc_info=True)


async def _persist_to_memory_safe(
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
