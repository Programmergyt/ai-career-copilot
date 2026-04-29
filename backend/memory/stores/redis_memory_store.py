"""Redis helpers for hot memory caches and recent memory events."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import redis.asyncio as aioredis

from memory.contracts import MemoryBundle, MemoryEvent


class RedisMemoryStore:
    """Redis-backed cache for recall results and recent memory events."""

    def __init__(self, client: aioredis.Redis, ttl: int = 60 * 60 * 24) -> None:
        self._client = client
        self._ttl = ttl

    async def load_recall_cache(
        self,
        *,
        session_id: str | None,
        user_id: str | None,
        query: str,
    ) -> MemoryBundle | None:
        raw = await self._client.get(self._recall_key(session_id, user_id, query))
        if not raw:
            return None
        return MemoryBundle.model_validate(json.loads(raw))

    async def save_recall_cache(
        self,
        *,
        session_id: str | None,
        user_id: str | None,
        query: str,
        bundle: MemoryBundle,
        ttl: int | None = None,
    ) -> None:
        await self._client.set(
            self._recall_key(session_id, user_id, query),
            bundle.model_dump_json(),
            ex=ttl or self._ttl,
        )

    async def append_event(self, event: MemoryEvent) -> None:
        key = self._events_key(event.session_id, event.user_id)
        await self._client.rpush(key, event.model_dump_json())
        await self._client.expire(key, self._ttl)

    async def get_recent_events(
        self,
        *,
        session_id: str | None,
        user_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        raw = await self._client.lrange(self._events_key(session_id, user_id), -limit, -1)
        return [json.loads(item) for item in raw]

    async def save_summary(
        self,
        *,
        session_id: str | None,
        user_id: str | None,
        summary: str,
        ttl: int | None = None,
    ) -> None:
        await self._client.set(self._summary_key(session_id, user_id), summary, ex=ttl or self._ttl)

    async def load_summary(self, *, session_id: str | None, user_id: str | None) -> str:
        return await self._client.get(self._summary_key(session_id, user_id)) or ""

    @staticmethod
    def _owner(session_id: str | None, user_id: str | None) -> str:
        if user_id:
            return f"user:{user_id}"
        if session_id:
            return f"session:{session_id}"
        return "global"

    def _recall_key(self, session_id: str | None, user_id: str | None, query: str) -> str:
        digest = hashlib.sha256((query or "").encode("utf-8")).hexdigest()[:24]
        return f"memory:recall:{self._owner(session_id, user_id)}:{digest}"

    def _events_key(self, session_id: str | None, user_id: str | None) -> str:
        return f"memory:events:{self._owner(session_id, user_id)}"

    def _summary_key(self, session_id: str | None, user_id: str | None) -> str:
        return f"memory:summary:{self._owner(session_id, user_id)}"
