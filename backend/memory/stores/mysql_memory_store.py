"""MySQL-backed memory truth store."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

import aiomysql

from memory.contracts import MemoryEvent, MemoryRecord, MemoryStatus
from log import get_logger

logger = get_logger("storage")


_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS memory_records (
        memory_id VARCHAR(64) PRIMARY KEY,
        user_id VARCHAR(64) NULL,
        session_id VARCHAR(64) NULL,
        scope ENUM('session', 'user', 'global') NOT NULL DEFAULT 'session',
        kind VARCHAR(32) NOT NULL,
        content TEXT NOT NULL,
        data JSON NOT NULL,
        source JSON NOT NULL,
        confidence DECIMAL(5,4) NOT NULL DEFAULT 1.0000,
        status ENUM('active', 'pending', 'archived', 'deleted') NOT NULL DEFAULT 'active',
        content_hash VARCHAR(64) NOT NULL DEFAULT '',
        embedding_status ENUM('pending', 'indexed', 'failed') NOT NULL DEFAULT 'pending',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        expires_at DATETIME NULL,
        INDEX idx_memory_owner (user_id, session_id),
        INDEX idx_memory_session (session_id),
        INDEX idx_memory_kind_status (kind, status),
        INDEX idx_memory_hash (content_hash)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_events (
        event_id VARCHAR(64) PRIMARY KEY,
        user_id VARCHAR(64) NULL,
        session_id VARCHAR(64) NULL,
        event_type VARCHAR(32) NOT NULL,
        memory_id VARCHAR(64) NULL,
        payload JSON NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_memory_events_owner (user_id, session_id),
        INDEX idx_memory_events_memory (memory_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_summaries (
        summary_id VARCHAR(64) PRIMARY KEY,
        user_id VARCHAR(64) NULL,
        session_id VARCHAR(64) NULL,
        scope ENUM('session', 'user', 'global') NOT NULL DEFAULT 'session',
        summary TEXT NOT NULL,
        source_memory_ids JSON NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_memory_summaries_owner (user_id, session_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]


class MySQLMemoryStore:
    """Persistence layer for memory records, events, and summaries."""

    def __init__(self, pool: aiomysql.Pool) -> None:
        self._pool = pool
        self._schema_ready = False

    async def ensure_schema(self) -> None:
        if self._schema_ready:
            return
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                for sql in _SCHEMA_STATEMENTS:
                    await cur.execute(sql)
            await conn.commit()
        self._schema_ready = True
        logger.info("Memory MySQL schema is ready")

    async def upsert_memory(self, record: MemoryRecord, embedding_status: str = "pending") -> None:
        await self.ensure_schema()
        now = _mysql_now()
        sql = """
            INSERT INTO memory_records
                (memory_id, user_id, session_id, scope, kind, content, data, source,
                 confidence, status, content_hash, embedding_status, created_at, updated_at, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            AS new_row
            ON DUPLICATE KEY UPDATE
                user_id = new_row.user_id,
                session_id = new_row.session_id,
                scope = new_row.scope,
                kind = new_row.kind,
                content = new_row.content,
                data = new_row.data,
                source = new_row.source,
                confidence = new_row.confidence,
                status = new_row.status,
                content_hash = new_row.content_hash,
                embedding_status = new_row.embedding_status,
                updated_at = new_row.updated_at,
                expires_at = new_row.expires_at
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (
                    record.memory_id,
                    record.user_id,
                    record.session_id,
                    _enum_value(record.scope),
                    _enum_value(record.kind),
                    record.content,
                    json.dumps(record.data, ensure_ascii=False, default=str),
                    json.dumps(record.source, ensure_ascii=False, default=str),
                    float(record.confidence),
                    _enum_value(record.status),
                    record.content_hash,
                    embedding_status,
                    now,
                    now,
                    _to_mysql_datetime(record.expires_at),
                ))
            await conn.commit()
        logger.debug("Upserted memory %s kind=%s", record.memory_id, record.kind)

    async def mark_embedding_status(self, memory_id: str, status: str) -> None:
        await self.ensure_schema()
        sql = "UPDATE memory_records SET embedding_status = %s WHERE memory_id = %s"
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (status, memory_id))
            await conn.commit()

    async def get_memory(self, memory_id: str) -> MemoryRecord | None:
        await self.ensure_schema()
        sql = "SELECT * FROM memory_records WHERE memory_id = %s"
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (memory_id,))
                row = await cur.fetchone()
        return _record_from_row(row) if row else None

    async def list_memories(
        self,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        kind: str | None = None,
        status: str | None = MemoryStatus.ACTIVE.value,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        await self.ensure_schema()
        where: list[str] = []
        params: list[Any] = []

        if user_id:
            where.append("(user_id = %s OR session_id = %s OR scope = 'global')")
            params.extend([user_id, session_id or ""])
        elif session_id:
            where.append("(session_id = %s OR scope = 'global')")
            params.append(session_id)
        else:
            where.append("scope = 'global'")

        if kind:
            where.append("kind = %s")
            params.append(kind)
        if status:
            where.append("status = %s")
            params.append(status)

        where.append("(expires_at IS NULL OR expires_at > UTC_TIMESTAMP())")
        sql = f"""
            SELECT * FROM memory_records
            WHERE {' AND '.join(where)}
            ORDER BY updated_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([max(1, min(limit, 200)), max(0, offset)])

        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, params)
                rows = await cur.fetchall()
        return [_record_from_row(row) for row in rows if row]

    async def soft_delete_memory(self, memory_id: str) -> None:
        await self.ensure_schema()
        sql = "UPDATE memory_records SET status = 'deleted', updated_at = %s WHERE memory_id = %s"
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (_mysql_now(), memory_id))
            await conn.commit()

    async def update_memory(
        self,
        memory_id: str,
        *,
        content: str | None = None,
        data: dict[str, Any] | None = None,
        status: str | None = None,
        content_hash: str | None = None,
    ) -> MemoryRecord | None:
        await self.ensure_schema()
        assignments: list[str] = []
        params: list[Any] = []
        if content is not None:
            assignments.append("content = %s")
            params.append(content)
        if data is not None:
            assignments.append("data = %s")
            params.append(json.dumps(data, ensure_ascii=False, default=str))
        if status is not None:
            assignments.append("status = %s")
            params.append(status)
        if content_hash is not None:
            assignments.append("content_hash = %s")
            params.append(content_hash)
        if not assignments:
            return await self.get_memory(memory_id)

        assignments.append("updated_at = %s")
        params.append(_mysql_now())
        params.append(memory_id)
        sql = f"UPDATE memory_records SET {', '.join(assignments)} WHERE memory_id = %s"
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
            await conn.commit()
        return await self.get_memory(memory_id)

    async def append_event(self, event: MemoryEvent) -> None:
        await self.ensure_schema()
        sql = """
            INSERT INTO memory_events
                (event_id, user_id, session_id, event_type, memory_id, payload, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            AS new_row
            ON DUPLICATE KEY UPDATE payload = new_row.payload
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (
                    event.event_id,
                    event.user_id,
                    event.session_id,
                    event.event_type,
                    event.memory_id,
                    json.dumps(event.payload, ensure_ascii=False, default=str),
                    _to_mysql_datetime(event.created_at) or _mysql_now(),
                ))
            await conn.commit()

    async def upsert_summary(
        self,
        *,
        summary_id: str,
        user_id: str | None,
        session_id: str | None,
        scope: str,
        summary: str,
        source_memory_ids: list[str],
    ) -> None:
        await self.ensure_schema()
        sql = """
            INSERT INTO memory_summaries
                (summary_id, user_id, session_id, scope, summary, source_memory_ids, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            AS new_row
            ON DUPLICATE KEY UPDATE
                summary = new_row.summary,
                source_memory_ids = new_row.source_memory_ids,
                updated_at = new_row.updated_at
        """
        now = _mysql_now()
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (
                    summary_id,
                    user_id,
                    session_id,
                    scope,
                    summary,
                    json.dumps(source_memory_ids, ensure_ascii=False),
                    now,
                    now,
                ))
            await conn.commit()


def _record_from_row(row: dict[str, Any]) -> MemoryRecord:
    data = _json_value(row.get("data"), {})
    source = _json_value(row.get("source"), {})
    confidence = row.get("confidence", 1.0)
    if isinstance(confidence, Decimal):
        confidence = float(confidence)
    return MemoryRecord(
        memory_id=row["memory_id"],
        user_id=row.get("user_id"),
        session_id=row.get("session_id"),
        scope=row.get("scope") or "session",
        kind=row.get("kind") or "profile_fact",
        content=row.get("content") or "",
        data=data,
        source=source,
        confidence=float(confidence),
        status=row.get("status") or "active",
        content_hash=row.get("content_hash") or "",
        created_at=_to_iso(row.get("created_at")),
        updated_at=_to_iso(row.get("updated_at")),
        expires_at=_to_iso(row.get("expires_at")) if row.get("expires_at") else None,
    )


def _enum_value(value: Any) -> str:
    return getattr(value, "value", str(value))


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        return json.loads(value)
    return value


def _mysql_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _to_mysql_datetime(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace("T", " ").replace("Z", "").split("+")[0].split(".")[0]


def _to_iso(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
