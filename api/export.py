"""POST /api/export — 导出接口（MVP 预留）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from storage.redis_client import RedisSessionStore
from workflow.state import CopilotState
from log import get_logger

logger = get_logger("api")

router = APIRouter(prefix="/api", tags=["export"])


class ExportRequest(BaseModel):
    session_id: str
    format: str = "html"  # html / json / markdown


@router.post("/export")
async def export_resume(req: ExportRequest):
    """导出简历。MVP 阶段一支持 html 和 json 格式。"""
    store = RedisSessionStore(req.session_id)
    saved = store.load_state()
    if not saved:
        raise HTTPException(status_code=404, detail="会话不存在")

    state = CopilotState.model_validate(saved)

    if req.format == "html":
        if not state.resume_html.html:
            raise HTTPException(status_code=404, detail="简历 HTML 尚未生成")
        return Response(
            content=state.resume_html.html,
            media_type="text/html",
            headers={"Content-Disposition": "attachment; filename=resume.html"},
        )

    elif req.format == "json":
        if state.resume_content_json is None:
            raise HTTPException(status_code=404, detail="简历内容尚未生成")
        import json
        content = json.dumps(state.resume_content_json.model_dump(), ensure_ascii=False, indent=2)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=resume.json"},
        )

    elif req.format == "markdown":
        raise HTTPException(status_code=501, detail="Markdown 导出将在后续版本中支持")

    elif req.format == "pdf":
        raise HTTPException(status_code=501, detail="PDF 导出将在后续版本中支持")

    else:
        raise HTTPException(status_code=400, detail=f"不支持的格式: {req.format}")
