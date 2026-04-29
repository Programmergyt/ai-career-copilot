"""Memory management API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from memory.service import get_memory_service
from log import get_logger

logger = get_logger("api")

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryCreateRequest(BaseModel):
    session_id: str | None = None
    user_id: str | None = None
    kind: str = "preference"
    content: str
    data: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0


class MemoryUpdateRequest(BaseModel):
    content: str | None = None
    data: dict[str, Any] | None = None
    status: str | None = None


@router.get("")
async def list_memories(
    session_id: str | None = None,
    user_id: str | None = None,
    kind: str | None = None,
    status: str | None = "active",
    limit: int = 50,
    offset: int = 0,
):
    """List memories for a session or future user id."""
    if not session_id and not user_id:
        raise HTTPException(status_code=400, detail="session_id 或 user_id 至少提供一个")
    service = await get_memory_service()
    records = await service.list_memories(
        session_id=session_id,
        user_id=user_id,
        kind=kind,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {"memories": [record.model_dump() for record in records]}


@router.post("")
async def create_memory(req: MemoryCreateRequest):
    """Create a manual memory. Useful for explicit user preferences."""
    if not req.session_id and not req.user_id:
        raise HTTPException(status_code=400, detail="session_id 或 user_id 至少提供一个")
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="content 不能为空")
    service = await get_memory_service()
    record = await service.create_manual_memory(
        session_id=req.session_id,
        user_id=req.user_id,
        kind=req.kind,
        content=req.content,
        data=req.data,
        source=req.source,
        confidence=req.confidence,
    )
    return {"memory": record.model_dump()}


@router.patch("/{memory_id}")
async def update_memory(memory_id: str, req: MemoryUpdateRequest):
    """Update content/data/status for one memory."""
    service = await get_memory_service()
    record = await service.update_memory(
        memory_id,
        content=req.content,
        data=req.data,
        status=req.status,
    )
    if not record:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"memory": record.model_dump()}


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    """Soft delete one memory and remove it from Chroma index."""
    service = await get_memory_service()
    await service.delete_memory(memory_id)
    return {"status": "deleted", "memory_id": memory_id}
