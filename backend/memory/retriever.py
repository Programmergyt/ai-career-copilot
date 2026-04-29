"""Hybrid structured/vector memory retrieval."""

from __future__ import annotations

from memory.contracts import MemoryBundle, MemoryHit, MemoryQuery, MemoryRecord
from memory.stores.chroma_memory_index import ChromaMemoryIndex
from memory.stores.mysql_memory_store import MySQLMemoryStore
from models.rerank import arerank_texts
from log import get_logger

logger = get_logger("storage")


class MemoryRetriever:
    """Combines MySQL structured lookup, Chroma vector search, and optional rerank."""

    def __init__(self, mysql_store: MySQLMemoryStore, chroma_index: ChromaMemoryIndex) -> None:
        self._mysql = mysql_store
        self._chroma = chroma_index

    async def retrieve(self, query: MemoryQuery) -> MemoryBundle:
        structured = await self._structured_hits(query)
        vector = await self._vector_hits(query)
        merged = await self._merge_hits(structured + vector)

        if query.use_rerank and query.query and len(merged) > 1:
            merged = await self._rerank(query, merged)
        else:
            merged.sort(key=lambda item: item.score, reverse=True)

        hits = merged[: query.top_k]
        return MemoryBundle(hits=hits, summary=_build_summary(hits))

    async def _structured_hits(self, query: MemoryQuery) -> list[MemoryHit]:
        allowed_kinds = [_enum_value(kind) for kind in query.kinds]
        if allowed_kinds:
            records: list[MemoryRecord] = []
            for kind in allowed_kinds:
                records.extend(await self._mysql.list_memories(
                    user_id=query.user_id,
                    session_id=query.session_id,
                    kind=kind,
                    limit=max(query.top_k * 2, 10),
                ))
        else:
            records = await self._mysql.list_memories(
                user_id=query.user_id,
                session_id=query.session_id,
                limit=max(query.top_k * 3, 20),
            )
        return [
            MemoryHit(record=record, score=_structured_score(record), source="mysql", reason="structured")
            for record in records
        ]

    async def _vector_hits(self, query: MemoryQuery) -> list[MemoryHit]:
        if not query.use_vector or not query.query:
            return []
        try:
            hits = await self._chroma.query(query)
        except Exception as exc:
            logger.warning("Chroma memory recall failed: %s", exc)
            return []

        hydrated: list[MemoryHit] = []
        for hit in hits:
            record = await self._mysql.get_memory(hit.record.memory_id)
            if not record:
                continue
            hydrated.append(hit.model_copy(update={"record": record}))
        return hydrated

    async def _merge_hits(self, hits: list[MemoryHit]) -> list[MemoryHit]:
        by_id: dict[str, MemoryHit] = {}
        for hit in hits:
            existing = by_id.get(hit.record.memory_id)
            if existing is None or hit.score > existing.score:
                by_id[hit.record.memory_id] = hit
        return list(by_id.values())

    async def _rerank(self, query: MemoryQuery, hits: list[MemoryHit]) -> list[MemoryHit]:
        try:
            ranked = await arerank_texts(
                [hit.record.content for hit in hits],
                query.query,
                top_n=min(len(hits), max(query.top_k, 5)),
            )
        except Exception as exc:
            logger.warning("Memory rerank failed: %s", exc)
            hits.sort(key=lambda item: item.score, reverse=True)
            return hits

        reranked: list[MemoryHit] = []
        used: set[int] = set()
        for item in ranked:
            index = item.get("index")
            if index is None or index in used or index >= len(hits):
                continue
            used.add(index)
            score = float(item.get("relevance_score", hits[index].score))
            reranked.append(hits[index].model_copy(update={"score": score, "reason": "rerank"}))

        for index, hit in enumerate(hits):
            if index not in used:
                reranked.append(hit)
        return reranked


def _structured_score(record: MemoryRecord) -> float:
    kind = _enum_value(record.kind)
    if kind == "preference":
        return 0.78
    if kind == "profile_fact":
        return 0.72
    if kind == "summary":
        return 0.68
    return 0.55


def _build_summary(hits: list[MemoryHit]) -> str:
    if not hits:
        return ""
    lines = []
    for index, hit in enumerate(hits[:8], start=1):
        kind = _enum_value(hit.record.kind)
        content = hit.record.content.strip()
        if len(content) > 500:
            content = content[:500].rstrip() + "..."
        lines.append(f"{index}. [{kind}] {content}")
    return "\n".join(lines)


def _enum_value(value) -> str:
    return getattr(value, "value", str(value))
