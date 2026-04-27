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
        state = CopilotState.model_validate(saved_state)
    else:
        state = CopilotState(session_id=session_id)

    # 注入用户输入
    prepared_input = prepare_chat_input(req.message, req.attachments)
    state.user_message = prepared_input.user_message
    state.user_attachments = prepared_input.user_attachments

    # 执行 workflow graph，加上config指定langsmith的run_name，方便在LangSmith上查看每次API调用的执行详情
    graph = _get_graph()
    try:
        result = await _ainvoke_graph(graph, state.model_dump(), config={"run_name": f"API-Chat-Request: {session_id}"})
    except Exception as e:
        logger.error("Workflow execution failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理失败: {e}")

    # 构建响应状态
    final_state = CopilotState.model_validate(result)

    # 持久化到 Redis
    persist_data = final_state.model_dump(exclude={"user_message", "user_attachments", "current_intent",
                                                     "execution_plan", "reply_message", "triggered_agents",
                                                     "workflow_trace"})
    await _asave_state(store, persist_data)

    # 后台持久化到 MySQL，避免同步阻塞请求主链。
    background_tasks.add_task(_persist_to_mysql_safe, final_state)

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
