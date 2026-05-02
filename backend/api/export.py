"""POST /api/export — 导出接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from services.export_service import ExportError, ExportResult, export_state
from services.session_service import SessionNotFoundError, load_existing_state

router = APIRouter(prefix="/api", tags=["export"])


class ExportRequest(BaseModel):
    session_id: str
    format: str = "html"  # html / json / markdown / txt / md
    target: str = "resume"  # resume / job / gaps / interview


def _build_response(result: ExportResult) -> Response:
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={"Content-Disposition": f"attachment; filename={result.filename}"},
    )


@router.post("/export")
async def export_resume(req: ExportRequest):
    """导出简历、岗位解析、缺失信息或面试问答。"""
    try:
        state = await load_existing_state(req.session_id)
        result = export_state(state, req.target, req.format)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="会话不存在") from exc
    except ExportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return _build_response(result)
