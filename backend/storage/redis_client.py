"""Redis 客户端封装：基于 redis.asyncio 的异步会话状态读写。"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from config_loader import get_redis_config
from log import get_logger

logger = get_logger("storage")

_redis_client: aioredis.Redis | None = None

# 默认 TTL 24 小时
_DEFAULT_TTL = 60 * 60 * 24


async def get_redis_client() -> aioredis.Redis:
    """获取 Redis 异步连接（单例）。"""
    global _redis_client
    if _redis_client is None:
        cfg = get_redis_config()
        _redis_client = aioredis.Redis(
            host=cfg["host"],
            port=cfg["port"],
            db=cfg["db"],
            password=cfg.get("password") or None,
            decode_responses=True,
        )
        logger.info("Redis async client initialized: %s:%s db=%s", cfg["host"], cfg["port"], cfg["db"])
    return _redis_client


class RedisSessionStore:
    """会话级 Redis 异步状态管理。"""

    def __init__(self, session_id: str, client: aioredis.Redis, ttl: int = _DEFAULT_TTL):
        self.session_id = session_id
        self.ttl = ttl
        self._client = client

    # ---- key helpers ----
    def _state_key(self) -> str:
        return f"session:{self.session_id}:state"

    def _events_key(self) -> str:
        return f"session:{self.session_id}:events"

    def _lock_key(self) -> str:
        return f"session:{self.session_id}:lock"

    # ---- state CRUD ----
    async def save_state(self, state: dict[str, Any]) -> None:
        key = self._state_key()
        await self._client.set(key, json.dumps(state, ensure_ascii=False, default=str), ex=self.ttl)
        logger.debug("Saved state for session %s", self.session_id)

    async def load_state(self) -> dict[str, Any] | None:
        data = await self._client.get(self._state_key())
        if data is None:
            return None
        return json.loads(data)

    async def delete_state(self) -> None:
        await self._client.delete(self._state_key(), self._events_key())
        logger.info("Deleted state for session %s", self.session_id)

    # ---- events ----
    async def append_event(self, event: dict[str, Any]) -> None:
        await self._client.rpush(self._events_key(), json.dumps(event, ensure_ascii=False, default=str))
        await self._client.expire(self._events_key(), self.ttl)

    async def get_events(self) -> list[dict[str, Any]]:
        raw = await self._client.lrange(self._events_key(), 0, -1)
        return [json.loads(item) for item in raw]

    # ---- distributed lock ----
    async def acquire_lock(self, timeout: int = 30) -> bool:
        return bool(await self._client.set(self._lock_key(), "1", nx=True, ex=timeout))

    async def release_lock(self) -> None:
        await self._client.delete(self._lock_key())
