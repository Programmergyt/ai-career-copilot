"""ChromaDB vector index for semantic memory recall."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from memory.contracts import MemoryHit, MemoryQuery, MemoryRecord
from models.embedding import aembed_documents, aembed_query
from log import get_logger

logger = get_logger("storage")


class ChromaMemoryIndex:
    """Thin async adapter around ChromaDB PersistentClient."""

    def __init__(self, persist_directory: str, collection_name: str = "career_memory") -> None:
        self.persist_directory = str(Path(persist_directory).resolve())
        self.collection_name = collection_name
        self._collection = None
        self._available = False
        self._init_client()

    @property
    def available(self) -> bool:
        return self._available and self._collection is not None

    async def index_record(self, record: MemoryRecord) -> None:
        if not self.available or not record.content.strip():
            return
        embedding = await aembed_documents([record.content])
        metadata = _metadata(record)
        await asyncio.to_thread(
            self._collection.upsert,
            ids=[record.memory_id],
            documents=[record.content],
            metadatas=[metadata],
            embeddings=embedding,
        )

    async def delete_record(self, memory_id: str) -> None:
        if not self.available:
            return
        try:
            await asyncio.to_thread(self._collection.delete, ids=[memory_id])
        except Exception as exc:
            logger.warning("Chroma memory delete failed for %s: %s", memory_id, exc)

    async def query(self, query: MemoryQuery) -> list[MemoryHit]:
        if not self.available or not query.query.strip():
            return []
        embedding = await aembed_query(query.query)
        n_results = max(query.top_k * 5, query.top_k, 10)
        raw = await asyncio.to_thread(
            self._collection.query,
            query_embeddings=[embedding],
            n_results=n_results,
            where={"status": "active"},
            include=["documents", "metadatas", "distances"],
        )
        return _hits_from_chroma(raw, query)

    def _init_client(self) -> None:
        try:
            import chromadb
        except ImportError:
            logger.warning("chromadb is not installed; memory vector index disabled")
            return

        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=self.persist_directory)
        self._collection = client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._available = True
        logger.info("Chroma memory index ready at %s collection=%s", self.persist_directory, self.collection_name)


def _metadata(record: MemoryRecord) -> dict[str, str | int | float | bool]:
    source = record.source or {}
    return {
        "user_id": record.user_id or "",
        "session_id": record.session_id or "",
        "scope": _enum_value(record.scope),
        "kind": _enum_value(record.kind),
        "status": _enum_value(record.status),
        "source_type": str(source.get("type", "")),
        "source_id": str(source.get("id", "")),
        "updated_at": record.updated_at or "",
        "confidence": float(record.confidence),
    }


def _hits_from_chroma(raw: dict[str, Any], query: MemoryQuery) -> list[MemoryHit]:
    ids = (raw.get("ids") or [[]])[0]
    docs = (raw.get("documents") or [[]])[0]
    metadatas = (raw.get("metadatas") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]
    hits: list[MemoryHit] = []
    allowed_kinds = {_enum_value(kind) for kind in query.kinds} if query.kinds else set()

    for index, memory_id in enumerate(ids):
        metadata = metadatas[index] or {}
        if not _allowed_owner(metadata, query):
            continue
        if allowed_kinds and str(metadata.get("kind", "")) not in allowed_kinds:
            continue
        distance = float(distances[index]) if index < len(distances) else 1.0
        score = max(0.0, 1.0 - distance)
        record = MemoryRecord(
            memory_id=memory_id,
            user_id=metadata.get("user_id") or None,
            session_id=metadata.get("session_id") or None,
            scope=metadata.get("scope") or "session",
            kind=metadata.get("kind") or "artifact",
            content=docs[index] if index < len(docs) else "",
            source={"type": metadata.get("source_type", ""), "id": metadata.get("source_id", "")},
            confidence=float(metadata.get("confidence") or 1.0),
            status=metadata.get("status") or "active",
            updated_at=metadata.get("updated_at") or "",
        )
        hits.append(MemoryHit(record=record, score=score, source="chroma", reason="vector"))
        if len(hits) >= query.top_k:
            break
    return hits


def _allowed_owner(metadata: dict[str, Any], query: MemoryQuery) -> bool:
    if metadata.get("scope") == "global":
        return True
    if query.user_id and metadata.get("user_id") == query.user_id:
        return True
    if query.session_id and metadata.get("session_id") == query.session_id:
        return True
    return False


def _enum_value(value: Any) -> str:
    return getattr(value, "value", str(value))
