"""High-level memory service used by API/session layer."""

from __future__ import annotations

import uuid
from typing import Any

from config_loader import get_memory_config
from memory.context_adapter import MemoryContextAdapter
from memory.contracts import MemoryBundle, MemoryEvent, MemoryKind, MemoryQuery, MemoryRecord
from memory.extractor import MemoryExtractor
from memory.policy import build_memory_id, content_hash, should_index_kind, utc_now
from memory.retriever import MemoryRetriever
from memory.stores import ChromaMemoryIndex, MySQLMemoryStore, RedisMemoryStore
from storage.mysql_client import get_mysql_pool
from storage.redis_client import get_redis_client
from workflow.state import CopilotState
from log import get_logger

logger = get_logger("storage")

_memory_service: "MemoryService | None" = None


class MemoryService:
    """Facade for recall, write, management, and indexing."""

    def __init__(
        self,
        *,
        mysql_store: MySQLMemoryStore,
        redis_store: RedisMemoryStore,
        chroma_index: ChromaMemoryIndex,
        retriever: MemoryRetriever,
        extractor: MemoryExtractor,
        adapter: MemoryContextAdapter,
        enabled: bool = True,
        recall_top_k: int = 8,
        recall_cache_ttl: int = 300,
    ) -> None:
        self._mysql = mysql_store
        self._redis = redis_store
        self._chroma = chroma_index
        self._retriever = retriever
        self._extractor = extractor
        self._adapter = adapter
        self._enabled = enabled
        self._recall_top_k = recall_top_k
        self._recall_cache_ttl = recall_cache_ttl

    async def recall(
        self,
        *,
        session_id: str,
        message: str,
        state: CopilotState | None = None,
        user_id: str | None = None,
    ) -> MemoryBundle:
        if not self._enabled:
            return MemoryBundle()

        cached = await self._redis.load_recall_cache(session_id=session_id, user_id=user_id, query=message)
        if cached:
            return cached

        query = MemoryQuery(
            user_id=user_id,
            session_id=session_id,
            query=message,
            top_k=self._recall_top_k,
            use_vector=True,
            use_rerank=True,
        )
        bundle = await self._retriever.retrieve(query)
        await self._redis.save_recall_cache(
            session_id=session_id,
            user_id=user_id,
            query=message,
            bundle=bundle,
            ttl=self._recall_cache_ttl,
        )
        return bundle

    def format_context(self, bundle: MemoryBundle) -> str:
        return self._adapter.format_context(bundle)

    async def observe_and_write(
        self,
        *,
        old_state: CopilotState | None,
        final_state: CopilotState,
        user_message: str,
        user_id: str | None = None,
    ) -> None:
        if not self._enabled:
            return
        try:
            records = self._extractor.extract(
                old_state=old_state,
                final_state=final_state,
                user_message=user_message,
                user_id=user_id,
            )
            for record in records:
                await self.upsert_memory(record)
            if records:
                logger.info("Memory write completed: session=%s count=%d", final_state.session_id, len(records))
        except Exception as exc:
            logger.error("Memory observe/write failed: %s", exc, exc_info=True)

    async def upsert_memory(self, record: MemoryRecord) -> MemoryRecord:
        await self._mysql.upsert_memory(record, embedding_status="pending")
        event = MemoryEvent(
            event_id=f"mevt_{uuid.uuid4().hex[:16]}",
            user_id=record.user_id,
            session_id=record.session_id,
            event_type="upsert",
            memory_id=record.memory_id,
            payload={"kind": record.kind, "source": record.source},
            created_at=utc_now(),
        )
        await self._append_event_safe(event)

        if should_index_kind(record.kind):
            try:
                await self._chroma.index_record(record)
                await self._mysql.mark_embedding_status(record.memory_id, "indexed")
            except Exception as exc:
                await self._mysql.mark_embedding_status(record.memory_id, "failed")
                logger.warning("Memory vector indexing failed for %s: %s", record.memory_id, exc)
        return record

    async def create_manual_memory(
        self,
        *,
        session_id: str | None,
        user_id: str | None,
        kind: str,
        content: str,
        data: dict[str, Any] | None = None,
        source: dict[str, Any] | None = None,
        confidence: float = 1.0,
    ) -> MemoryRecord:
        source_id = (source or {}).get("id") or f"manual:{content_hash(content)[:16]}"
        record = MemoryRecord(
            memory_id=build_memory_id(kind=kind, source_id=str(source_id), user_id=user_id, session_id=session_id),
            user_id=user_id,
            session_id=session_id,
            scope="user" if user_id else "session",
            kind=kind,
            content=content,
            data=data or {},
            source=source or {"type": "manual", "id": source_id},
            confidence=confidence,
            status="active",
            content_hash=content_hash(content),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        return await self.upsert_memory(record)

    async def list_memories(
        self,
        *,
        session_id: str | None,
        user_id: str | None = None,
        kind: str | None = None,
        status: str | None = "active",
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        return await self._mysql.list_memories(
            user_id=user_id,
            session_id=session_id,
            kind=kind,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def update_memory(
        self,
        memory_id: str,
        *,
        content: str | None = None,
        data: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> MemoryRecord | None:
        record = await self._mysql.update_memory(
            memory_id,
            content=content,
            data=data,
            status=status,
            content_hash=content_hash(content) if content is not None else None,
        )
        if not record:
            return None
        if status == "deleted":
            await self._chroma.delete_record(memory_id)
        elif should_index_kind(record.kind):
            await self.upsert_memory(record)
        return record

    async def delete_memory(self, memory_id: str) -> None:
        record = await self._mysql.get_memory(memory_id)
        await self._mysql.soft_delete_memory(memory_id)
        await self._chroma.delete_record(memory_id)
        event = MemoryEvent(
            event_id=f"mevt_{uuid.uuid4().hex[:16]}",
            user_id=record.user_id if record else None,
            session_id=record.session_id if record else None,
            event_type="delete",
            memory_id=memory_id,
            payload={},
            created_at=utc_now(),
        )
        await self._append_event_safe(event)

    async def _append_event_safe(self, event: MemoryEvent) -> None:
        try:
            await self._mysql.append_event(event)
            await self._redis.append_event(event)
        except Exception as exc:
            logger.warning("Memory event append failed: %s", exc)


async def get_memory_service() -> MemoryService:
    global _memory_service
    if _memory_service is not None:
        return _memory_service

    cfg = get_memory_config()
    pool = await get_mysql_pool()
    redis_client = await get_redis_client()

    mysql_store = MySQLMemoryStore(pool)
    redis_store = RedisMemoryStore(redis_client, ttl=int(cfg.get("redis_ttl", 60 * 60 * 24)))
    chroma_index = ChromaMemoryIndex(
        persist_directory=cfg["chroma_persist_directory"],
        collection_name=cfg.get("chroma_collection", "career_memory"),
    )
    retriever = MemoryRetriever(mysql_store, chroma_index)
    _memory_service = MemoryService(
        mysql_store=mysql_store,
        redis_store=redis_store,
        chroma_index=chroma_index,
        retriever=retriever,
        extractor=MemoryExtractor(),
        adapter=MemoryContextAdapter(),
        enabled=bool(cfg.get("enabled", True)),
        recall_top_k=int(cfg.get("recall_top_k", 8)),
        recall_cache_ttl=int(cfg.get("recall_cache_ttl", 300)),
    )
    return _memory_service
