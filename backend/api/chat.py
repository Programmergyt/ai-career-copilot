"""POST /api/chat — 主对话接口。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from services.chat_input_service import ChatInputError, prepare_chat_input
from services.chat_orchestrator import (
    ContextWindowExceededError,
    WorkflowExecutionError,
    run_chat,
)
from services.persistence_service import add_background_persistence_tasks
from workflow.state import CopilotState

router = APIRouter(prefix="/api", tags=["chat"])


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
    try:
        prepared_input = prepare_chat_input(req.message, req.attachments)
    except ChatInputError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    try:
        result = await run_chat(
            session_id=req.session_id,
            user_message=prepared_input.user_message,
            user_attachments=prepared_input.user_attachments,
        )
    except ContextWindowExceededError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except WorkflowExecutionError as exc:
        raise HTTPException(status_code=500, detail=f"处理失败: {exc}") from exc

    add_background_persistence_tasks(
        background_tasks,
        previous_state=result.previous_state,
        final_state=result.final_state,
        user_message=result.user_message,
    )
    return _to_chat_response(result.final_state)


def _to_chat_response(final_state: CopilotState) -> ChatResponse:
    return ChatResponse(
        session_id=final_state.session_id,
        reply_message=final_state.reply_message,
        job=final_state.job.model_dump() if final_state.job else None,
        gaps=[g.model_dump() for g in final_state.gaps],
        questions_to_ask=[q.model_dump() for q in final_state.questions_to_ask],
        resume_content_json=final_state.resume_content_json.model_dump()
        if final_state.resume_content_json
        else None,
        render_config=final_state.render_config.model_dump(),
        resume_html=final_state.resume_html.model_dump(),
        interview_qa=[qa.model_dump() for qa in final_state.interview_qa],
        triggered_agents=final_state.triggered_agents,
        llm_token_usage=final_state.llm_token_usage,
        context_window=final_state.context_window,
    )
