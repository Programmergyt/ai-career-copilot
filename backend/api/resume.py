"""简历相关 API — GET/POST /api/resume/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from storage.redis_client import RedisSessionStore
from workflow.state import CopilotState
from log import get_logger

logger = get_logger("api")

router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.get("/content")
async def get_resume_content(session_id: str):
    """获取当前简历内容 JSON。"""
    store = RedisSessionStore(session_id)
    saved = store.load_state()
    if not saved:
        raise HTTPException(status_code=404, detail="会话不存在")
    state = CopilotState.model_validate(saved)
    if state.resume_content_json is None:
        raise HTTPException(status_code=404, detail="简历内容尚未生成")
    return {"resume_content_json": state.resume_content_json.model_dump()}


@router.get("/html")
async def get_resume_html(session_id: str):
    """获取当前简历 HTML。"""
    store = RedisSessionStore(session_id)
    saved = store.load_state()
    if not saved:
        raise HTTPException(status_code=404, detail="会话不存在")
    state = CopilotState.model_validate(saved)
    if not state.resume_html.html:
        raise HTTPException(status_code=404, detail="简历 HTML 尚未生成")
    return {"resume_html": state.resume_html.model_dump()}


@router.get("/preview")
async def preview_resume_html(session_id: str):
    """直接返回 HTML 用于浏览器预览。"""
    store = RedisSessionStore(session_id)
    saved = store.load_state()
    if not saved:
        raise HTTPException(status_code=404, detail="会话不存在")
    state = CopilotState.model_validate(saved)
    if not state.resume_html.html:
        raise HTTPException(status_code=404, detail="简历 HTML 尚未生成")
    return Response(content=state.resume_html.html, media_type="text/html")


class RenderRequest(BaseModel):
    session_id: str
    render_instruction: str


@router.post("/render")
async def render_resume(req: RenderRequest):
    """渲染指令接口。"""
    from api.chat import _get_graph, _persist_to_mysql

    store = RedisSessionStore(req.session_id)
    saved = store.load_state()
    if not saved:
        raise HTTPException(status_code=404, detail="会话不存在")

    state = CopilotState.model_validate(saved)
    state.user_message = req.render_instruction
    state.current_intent = "render_edit"
    state.execution_plan = ["render_agent"]

    graph = _get_graph()
    try:
        result = graph.invoke(state.model_dump())
    except Exception as e:
        logger.error("Render failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"渲染失败: {e}")

    final = CopilotState.model_validate(result)

    persist_data = final.model_dump(exclude={"user_message", "user_attachments", "current_intent",
                                              "execution_plan", "reply_message", "triggered_agents"})
    store.save_state(persist_data)

    try:
        _persist_to_mysql(final)
    except Exception as e:
        logger.error("MySQL persistence failed: %s", e, exc_info=True)

    return {
        "render_config": final.render_config.model_dump(),
        "resume_html": final.resume_html.model_dump(),
    }
