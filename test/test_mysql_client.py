# python -m pytest -sv test/test_mysql_client.py
# 注意：需要 MySQL 服务可用，属于集成测试
"""MySQL 客户端集成测试。

测试 MySQLStore 的 CRUD 操作，使用真实 MySQL 连接。
运行前请确保：
  1. MySQL 服务已启动
  2. 已执行 python -m sql.init_db 初始化数据库
"""

import json
import uuid
import pytest

from storage.mysql_client import MySQLStore


@pytest.fixture(scope="module")
def db():
    """创建 MySQLStore 实例（模块级别复用）。"""
    try:
        store = MySQLStore()
        return store
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {e}")


@pytest.fixture
def session_id(db):
    """创建一个测试用 session 并在测试后清理。"""
    sid = f"test_sess_{uuid.uuid4().hex[:8]}"
    db.upsert_session(sid)
    yield sid
    # 清理：由于 ON DELETE CASCADE，删除 session 会级联删除关联数据
    conn = db._conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE session_id = %s", (sid,))
        conn.commit()
    finally:
        conn.close()


class TestSessionCRUD:

    def test_upsert_session(self, db):
        sid = f"test_{uuid.uuid4().hex[:8]}"
        db.upsert_session(sid)
        # 验证可查到
        conn = db._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT session_id, status FROM sessions WHERE session_id = %s", (sid,))
                row = cur.fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row["session_id"] == sid
        assert row["status"] == "active"
        # 清理
        conn = db._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE session_id = %s", (sid,))
            conn.commit()
        finally:
            conn.close()

    def test_upsert_session_update_status(self, db, session_id):
        db.upsert_session(session_id, status="archived")
        conn = db._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM sessions WHERE session_id = %s", (session_id,))
                row = cur.fetchone()
        finally:
            conn.close()
        assert row["status"] == "archived"


class TestJobCRUD:

    def test_save_and_get_job(self, db, session_id):
        job_data = {
            "title": "AIGC工程师",
            "industry": "互联网",
            "tech_stack": ["Python", "LangChain"],
            "keywords": ["GenAI", "LLM"],
        }
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        db.save_job(job_id, session_id, job_data, version=1)
        result = db.get_job(session_id)
        assert result is not None
        assert result["title"] == "AIGC工程师"
        assert "Python" in result["tech_stack"]

    def test_save_job_version_update(self, db, session_id):
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        db.save_job(job_id, session_id, {"title": "v1"}, version=1)
        db.save_job(job_id, session_id, {"title": "v2"}, version=2)
        result = db.get_job(session_id)
        assert result["title"] == "v2"


class TestCandidateProfileCRUD:

    def test_save_and_get_profile(self, db, session_id):
        profile_data = {
            "profile_basic": {
                "name": "郭奕廷",
                "email": "2403508140@qq.com",
                "phone": "+86-13585926126",
                "city": "上海",
                "school": "华东理工大学",
            },
            "facts": [
                {"id": "f1", "type": "skill", "content": "Python"},
                {"id": "f2", "type": "skill", "content": "LangChain"},
            ],
        }
        profile_id = f"profile_{session_id}"
        db.save_candidate_profile(profile_id, session_id, profile_data)
        result = db.get_candidate_profile(session_id)
        assert result is not None
        assert result["profile_basic"]["name"] == "郭奕廷"
        assert len(result["facts"]) == 2


class TestResumeContentCRUD:

    def test_save_and_get_resume_content(self, db, session_id):
        content_data = {
            "profile": {"name": "郭奕廷"},
            "summary": "AI方向研究生",
            "skills": [{"id": "s1", "title": "Python", "content": "熟练"}],
        }
        content_id = f"content_{session_id}"
        db.save_resume_content(content_id, session_id, content_data, version=1, content_hash="abc123")
        result = db.get_resume_content(session_id)
        assert result is not None
        assert result["profile"]["name"] == "郭奕廷"


class TestRenderConfigCRUD:

    def test_save_and_get_render_config(self, db, session_id):
        config_data = {
            "template_id": "default",
            "theme": "light",
            "font_size": 14,
        }
        config_id = f"render_{session_id}"
        db.save_render_config(config_id, session_id, config_data)
        result = db.get_render_config(session_id)
        assert result is not None
        assert result["template_id"] == "default"


class TestResumeHTMLCRUD:

    def test_save_resume_html(self, db, session_id):
        html_id = f"html_{session_id}"
        html_str = "<html><body>Test Resume</body></html>"
        db.save_resume_html(html_id, session_id, html_str,
                            version=1, content_ver=1, render_ver=1, checksum="chk123")
        # 验证直接查询
        conn = db._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT html, checksum FROM resume_htmls WHERE id = %s", (html_id,))
                row = cur.fetchone()
        finally:
            conn.close()
        assert row is not None
        assert "Test Resume" in row["html"]
        assert row["checksum"] == "chk123"


class TestEventCRUD:

    def test_save_event(self, db, session_id):
        event = {
            "event_id": f"evt_{uuid.uuid4().hex[:8]}",
            "session_id": session_id,
            "message_id": "msg_001",
            "intent": "upload_jd",
            "triggered_agents": ["jd_agent", "content_agent"],
            "state_diff_summary": {"job": "created"},
            "status": "success",
        }
        db.save_event(event)
        conn = db._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT intent, status FROM conversation_events WHERE event_id = %s",
                            (event["event_id"],))
                row = cur.fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row["intent"] == "upload_jd"
        assert row["status"] == "success"
