"""简历相关 API — GET/POST /api/resume/*"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from pydantic import BaseModel

from storage.redis_client import get_redis_client, RedisSessionStore
from workflow.state import CopilotState
from log import get_logger

logger = get_logger("api")

router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.get("/content")
async def get_resume_content(session_id: str):
    """获取当前简历内容 JSON。"""
    from api.chat import _aload_state

    client = await get_redis_client()
    store = RedisSessionStore(session_id, client)
    saved = await _aload_state(store)
    if not saved:
        raise HTTPException(status_code=404, detail="会话不存在")
    state = CopilotState.model_validate(saved)
    if state.resume_content_json is None:
        raise HTTPException(status_code=404, detail="简历内容尚未生成")
    return {"resume_content_json": state.resume_content_json.model_dump()}


@router.get("/html")
async def get_resume_html(session_id: str):
    """获取当前简历 HTML。"""
    from api.chat import _aload_state

    client = await get_redis_client()
    store = RedisSessionStore(session_id, client)
    saved = await _aload_state(store)
    if not saved:
        raise HTTPException(status_code=404, detail="会话不存在")
    state = CopilotState.model_validate(saved)
    if not state.resume_html.html:
        raise HTTPException(status_code=404, detail="简历 HTML 尚未生成")
    return {"resume_html": state.resume_html.model_dump()}


@router.get("/preview")
async def preview_resume_html(session_id: str):
    """直接返回 HTML 用于浏览器预览。"""
    from api.chat import _aload_state

    client = await get_redis_client()
    store = RedisSessionStore(session_id, client)
    saved = await _aload_state(store)
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
async def render_resume(req: RenderRequest, background_tasks: BackgroundTasks):
    """渲染指令接口。"""
    from api.chat import _ainvoke_graph, _aload_state, _asave_state, _get_graph, _persist_to_mysql_safe

    client = await get_redis_client()
    store = RedisSessionStore(req.session_id, client)
    saved = await _aload_state(store)
    if not saved:
        raise HTTPException(status_code=404, detail="会话不存在")

    state = CopilotState.model_validate(saved)
    state.user_message = req.render_instruction
    state.current_intent = "render_edit"
    state.execution_plan = ["render_agent"]

    graph = _get_graph()
    try:
        result = await _ainvoke_graph(graph, state.model_dump())
    except Exception as e:
        logger.error("Render failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"渲染失败: {e}")

    final = CopilotState.model_validate(result)

    persist_data = final.model_dump(exclude={"user_message", "user_attachments", "current_intent",
                                              "execution_plan", "reply_message", "triggered_agents",
                                              "workflow_trace"})
    await _asave_state(store, persist_data)

    background_tasks.add_task(_persist_to_mysql_safe, final)

    return {
        "render_config": final.render_config.model_dump(),
        "resume_html": final.resume_html.model_dump(),
    }
