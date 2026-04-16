# 示例: 在项目根目录执行 pytest backend/test/storage/test_redis_client.py -sv
# 注意：需要 Redis 服务可用，属于集成测试
"""Redis 客户端集成测试。

测试 RedisSessionStore 的状态读写、事件追加和分布式锁操作。
运行前请确保 Redis 服务已启动。
"""

import json
import uuid
import pytest

from storage.redis_client import RedisSessionStore, get_redis_client


@pytest.fixture
def store():
    """创建一个测试用 RedisSessionStore，测试后清理。"""
    try:
        session_id = f"test_sess_{uuid.uuid4().hex[:8]}"
        s = RedisSessionStore(session_id, ttl=60)  # 短 TTL 用于测试
        yield s
        s.delete_state()
    except Exception as e:
        pytest.skip(f"Redis 不可用: {e}")


class TestRedisConnection:

    def test_ping(self):
        try:
            client = get_redis_client()
            assert client.ping() is True
        except Exception as e:
            pytest.skip(f"Redis 不可用: {e}")


class TestStateCRUD:

    def test_save_and_load_state(self, store):
        state = {
            "session_id": store.session_id,
            "job": {"title": "AIGC工程师", "tech_stack": ["Python"]},
            "candidate_profile": {"profile_basic": {"name": "郭奕廷"}},
        }
        store.save_state(state)
        loaded = store.load_state()
        assert loaded is not None
        assert loaded["session_id"] == store.session_id
        assert loaded["job"]["title"] == "AIGC工程师"

    def test_load_nonexistent_state(self, store):
        loaded = store.load_state()
        assert loaded is None

    def test_overwrite_state(self, store):
        store.save_state({"version": 1})
        store.save_state({"version": 2})
        loaded = store.load_state()
        assert loaded["version"] == 2

    def test_delete_state(self, store):
        store.save_state({"test": True})
        store.delete_state()
        loaded = store.load_state()
        assert loaded is None


class TestEvents:

    def test_append_and_get_events(self, store):
        store.append_event({"intent": "upload_jd", "status": "success"})
        store.append_event({"intent": "upload_profile", "status": "success"})
        events = store.get_events()
        assert len(events) == 2
        assert events[0]["intent"] == "upload_jd"
        assert events[1]["intent"] == "upload_profile"

    def test_empty_events(self, store):
        events = store.get_events()
        assert events == []


class TestDistributedLock:

    def test_acquire_and_release_lock(self, store):
        acquired = store.acquire_lock(timeout=5)
        assert acquired is True
        store.release_lock()

    def test_lock_is_exclusive(self, store):
        acquired1 = store.acquire_lock(timeout=5)
        assert acquired1 is True
        # 同一个 session 再次获取应失败
        acquired2 = store.acquire_lock(timeout=5)
        assert acquired2 is False
        store.release_lock()

    def test_lock_release_allows_reacquire(self, store):
        store.acquire_lock(timeout=5)
        store.release_lock()
        acquired = store.acquire_lock(timeout=5)
        assert acquired is True
        store.release_lock()
