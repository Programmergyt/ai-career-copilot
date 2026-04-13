# python -m pytest -sv test/test_api.py
# 注意：需要 Redis 和 MySQL 服务可用，属于集成测试
"""FastAPI API 接口测试。

使用 TestClient 测试各 API 路由的请求/响应结构。
"""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient。"""
    return TestClient(app)


class TestHealthEndpoint:

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestChatEndpoint:

    def test_chat_requires_message(self, client):
        """不提供 message 应返回 422。"""
        response = client.post("/api/chat", json={})
        assert response.status_code == 422

    def test_chat_request_structure(self, client):
        """验证请求结构被正确接受（可能因 LLM 不可用而 500，但结构不应 422）。"""
        response = client.post("/api/chat", json={
            "message": "你好",
        })
        # 可能 200 或 500（依赖 LLM），但不应是 422
        assert response.status_code != 422


class TestResumeEndpoints:

    def test_get_content_without_session(self, client):
        """不存在的 session 应返回 404。"""
        response = client.get("/api/resume/content", params={"session_id": "nonexistent_session"})
        assert response.status_code == 404

    def test_get_html_without_session(self, client):
        response = client.get("/api/resume/html", params={"session_id": "nonexistent_session"})
        assert response.status_code == 404

    def test_preview_without_session(self, client):
        response = client.get("/api/resume/preview", params={"session_id": "nonexistent_session"})
        assert response.status_code == 404

    def test_render_requires_session(self, client):
        response = client.post("/api/resume/render", json={
            "session_id": "nonexistent_session",
            "render_instruction": "改大字号",
        })
        assert response.status_code == 404


class TestExportEndpoint:

    def test_export_without_session(self, client):
        response = client.post("/api/export", json={
            "session_id": "nonexistent_session",
            "format": "html",
        })
        assert response.status_code == 404

    def test_export_unsupported_format(self, client):
        """不支持的格式应返回 400（如果 session 存在）或 404。"""
        response = client.post("/api/export", json={
            "session_id": "nonexistent_session",
            "format": "xml",
        })
        # session 不存在时先返回 404
        assert response.status_code in (400, 404)
