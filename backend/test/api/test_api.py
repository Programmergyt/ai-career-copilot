# 示例: 在项目根目录执行 pytest backend/test/api/test_api.py -sv
# 注意：需要 Redis 和 MySQL 服务可用，属于集成测试
"""FastAPI API 接口测试。

使用 TestClient 测试各 API 路由的请求/响应结构。
"""

import json

import pytest
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

pytest.importorskip("aiomysql")
pytest.importorskip("redis")

from main import app
from api.chat import ChatResponse
from workflow.plan_mode.plan_schema import ContractViolation, PlanStep, StepPrecondition, StepRetryPolicy, StepResult
from workflow.state import CopilotState, Gap, InterviewQA, Job, Question


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

    def test_chat_response_model_contains_plan_debug_fields(self):
        payload = ChatResponse(
            session_id="sess_api",
            reply_message="ok",
            plan_id="plan_1",
            plan_status="success",
            execution_steps=[
                PlanStep(
                    step_id="st_1",
                    agent="render_agent",
                    action="render_resume",
                    intent="render_edit",
                    preconditions=[StepPrecondition(kind="resume_content_exists")],
                    retry=StepRetryPolicy(),
                ).model_dump()
            ],
            step_results=[
                StepResult(
                    step_id="st_1",
                    agent="render_agent",
                    action="render_resume",
                    status="success",
                    attempt=1,
                ).model_dump()
            ],
            contract_violations=[
                ContractViolation(
                    step_id="st_1",
                    agent="render_agent",
                    action="render_resume",
                    field="resume_content_json",
                    reason="write_not_allowed_by_contract",
                ).model_dump()
            ],
        )

        assert payload.plan_id == "plan_1"
        assert payload.plan_status == "success"
        assert payload.execution_steps[0]["action"] == "render_resume"


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

    def test_export_job_txt(self, client, monkeypatch):
        saved_state = CopilotState(
            session_id="sess_export_job",
            job=Job(
                id="job_1",
                title="AI Engineer Intern",
                industry="Internet",
                tech_stack=["Python", "LangChain"],
                hard_skills=["RAG"],
                responsibilities=["Build AI workflows"],
            ),
        ).model_dump()

        class DummyStore:
            def __init__(self, session_id):
                self.session_id = session_id

            def load_state(self):
                return saved_state

        monkeypatch.setattr("api.export.RedisSessionStore", DummyStore)

        response = client.post("/api/export", json={
            "session_id": "sess_export_job",
            "target": "job",
            "format": "txt",
        })

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert "岗位解析" in response.text
        assert "AI Engineer Intern" in response.text

    def test_export_gaps_json(self, client, monkeypatch):
        saved_state = CopilotState(
            session_id="sess_export_gaps",
            gaps=[
                Gap(
                    id="gap_1",
                    type="missing_skill",
                    severity="high",
                    description="缺少生产级 RAG 经验",
                )
            ],
            questions_to_ask=[
                Question(
                    id="q_1",
                    question="你是否做过线上 RAG 项目？",
                    reason="确认项目深度",
                    target_field="projects",
                    priority="high",
                )
            ],
        ).model_dump()

        class DummyStore:
            def __init__(self, session_id):
                self.session_id = session_id

            def load_state(self):
                return saved_state

        monkeypatch.setattr("api.export.RedisSessionStore", DummyStore)

        response = client.post("/api/export", json={
            "session_id": "sess_export_gaps",
            "target": "gaps",
            "format": "json",
        })

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        payload = json.loads(response.text)
        assert payload["gaps"][0]["description"] == "缺少生产级 RAG 经验"
        assert payload["questions_to_ask"][0]["target_field"] == "projects"

    def test_export_interview_markdown(self, client, monkeypatch):
        saved_state = CopilotState(
            session_id="sess_export_interview",
            interview_qa=[
                InterviewQA(
                    id="qa_1",
                    category="technical",
                    question="How do you reduce hallucination in RAG?",
                    answer="I improve retrieval quality, grounding, and evaluation.",
                    source_refs=["proj_1"],
                )
            ],
        ).model_dump()

        class DummyStore:
            def __init__(self, session_id):
                self.session_id = session_id

            def load_state(self):
                return saved_state

        monkeypatch.setattr("api.export.RedisSessionStore", DummyStore)

        response = client.post("/api/export", json={
            "session_id": "sess_export_interview",
            "target": "interview",
            "format": "md",
        })

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/markdown")
        assert "# 面试问答" in response.text
        assert "How do you reduce hallucination in RAG?" in response.text
