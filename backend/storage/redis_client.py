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

    def __init__(
        self,
        session_id: str,
        client: aioredis.Redis,
        ttl: int = _DEFAULT_TTL,
        checkpoint_namespace: str = "live",
    ):
        self.session_id = session_id
        self.ttl = ttl
        self._client = client
        self.checkpoint_namespace = checkpoint_namespace

    # ---- key helpers ----
    def _state_key(self) -> str:
        return f"session:{self.session_id}:state"

    def _checkpoint_key(self, checkpoint_id: str) -> str:
        return f"session:{self.session_id}:checkpoint:{self.checkpoint_namespace}:{checkpoint_id}"

    def _checkpoint_index_key(self) -> str:
        return f"session:{self.session_id}:checkpoint:{self.checkpoint_namespace}:index"

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
        checkpoint_keys = await self._client.lrange(self._checkpoint_index_key(), 0, -1)
        await self._client.delete(
            self._state_key(),
            self._events_key(),
            self._checkpoint_index_key(),
            *checkpoint_keys,
        )
        logger.info("Deleted state for session %s", self.session_id)

    # ---- Redis Stack checkpoints ----
    async def save_checkpoint(self, checkpoint_id: str, state: dict[str, Any], metadata: dict[str, Any] | None = None) -> None:
        payload = {
            "session_id": self.session_id,
            "checkpoint_id": checkpoint_id,
            "namespace": self.checkpoint_namespace,
            "state": state,
            "metadata": metadata or {},
        }
        key = self._checkpoint_key(checkpoint_id)
        await self._json_set_with_fallback(key, payload)
        await self._client.expire(key, self.ttl)
        await self._client.lpush(self._checkpoint_index_key(), key)
        await self._client.ltrim(self._checkpoint_index_key(), 0, 49)
        await self._client.expire(self._checkpoint_index_key(), self.ttl)

    async def load_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        key = self._checkpoint_key(checkpoint_id)
        data = await self._json_get_with_fallback(key)
        if not data:
            return None
        return data

    async def latest_checkpoint(self) -> dict[str, Any] | None:
        keys = await self._client.lrange(self._checkpoint_index_key(), 0, 0)
        if not keys:
            return None
        return await self._json_get_with_fallback(keys[0])

    async def _json_set_with_fallback(self, key: str, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, default=str)
        try:
            await self._client.execute_command("JSON.SET", key, "$", encoded)
        except Exception as exc:
            logger.debug("RedisJSON unavailable for %s, falling back to string SET: %s", key, exc)
            await self._client.set(key, encoded)

    async def _json_get_with_fallback(self, key: str) -> dict[str, Any] | None:
        try:
            raw = await self._client.execute_command("JSON.GET", key, "$")
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return parsed[0]
                return parsed
        except Exception as exc:
            logger.debug("RedisJSON unavailable for %s, falling back to GET: %s", key, exc)
        raw = await self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

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
