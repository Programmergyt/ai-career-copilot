"""简历相关 API — GET/POST /api/resume/*"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from pydantic import BaseModel

from services.chat_orchestrator import WorkflowExecutionError, render_resume as render_resume_workflow
from services.persistence_service import add_background_persistence_tasks
from services.session_service import SessionNotFoundError, load_existing_state

router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.get("/content")
async def get_resume_content(session_id: str):
    """获取当前简历内容 JSON。"""
    try:
        state = await load_existing_state(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="会话不存在") from exc
    if state.resume_content_json is None:
        raise HTTPException(status_code=404, detail="简历内容尚未生成")
    return {"resume_content_json": state.resume_content_json.model_dump()}


@router.get("/html")
async def get_resume_html(session_id: str):
    """获取当前简历 HTML。"""
    try:
        state = await load_existing_state(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="会话不存在") from exc
    if not state.resume_html.html:
        raise HTTPException(status_code=404, detail="简历 HTML 尚未生成")
    return {"resume_html": state.resume_html.model_dump()}


@router.get("/preview")
async def preview_resume_html(session_id: str):
    """直接返回 HTML 用于浏览器预览。"""
    try:
        state = await load_existing_state(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="会话不存在") from exc
    if not state.resume_html.html:
        raise HTTPException(status_code=404, detail="简历 HTML 尚未生成")
    return Response(content=state.resume_html.html, media_type="text/html")


class RenderRequest(BaseModel):
    session_id: str
    render_instruction: str


@router.post("/render")
async def render_resume(req: RenderRequest, background_tasks: BackgroundTasks):
    """渲染指令接口。"""
    try:
        result = await render_resume_workflow(
            session_id=req.session_id,
            render_instruction=req.render_instruction,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="会话不存在") from exc
    except WorkflowExecutionError as exc:
        raise HTTPException(status_code=500, detail=f"渲染失败: {exc}") from exc

    final = result.final_state
    add_background_persistence_tasks(
        background_tasks,
        previous_state=result.previous_state,
        final_state=final,
        user_message=result.user_message,
    )

    return {
        "render_config": final.render_config.model_dump(),
        "resume_html": final.resume_html.model_dump(),
    }
