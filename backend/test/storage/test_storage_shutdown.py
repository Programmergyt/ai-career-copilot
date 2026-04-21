"""Tests for graceful shutdown of shared storage clients."""

from __future__ import annotations

import asyncio
import pytest

pytest.importorskip("aiomysql")
pytest.importorskip("redis")

from storage import mysql_client, redis_client


class _FakePool:
    def __init__(self) -> None:
        self.closed = False
        self.wait_closed_called = False

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        self.wait_closed_called = True


class _FakeRedisClient:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


def test_close_mysql_pool_closes_existing_pool():
    fake_pool = _FakePool()
    mysql_client._pool = fake_pool

    asyncio.run(mysql_client.close_mysql_pool())

    assert fake_pool.closed is True
    assert fake_pool.wait_closed_called is True
    assert mysql_client._pool is None


def test_close_mysql_pool_is_safe_when_uninitialized():
    mysql_client._pool = None

    asyncio.run(mysql_client.close_mysql_pool())

    assert mysql_client._pool is None


def test_close_redis_client_closes_existing_client():
    fake_client = _FakeRedisClient()
    redis_client._redis_client = fake_client

    asyncio.run(redis_client.close_redis_client())

    assert fake_client.closed is True
    assert redis_client._redis_client is None


def test_close_redis_client_is_safe_when_uninitialized():
    redis_client._redis_client = None

    asyncio.run(redis_client.close_redis_client())

    assert redis_client._redis_client is None
