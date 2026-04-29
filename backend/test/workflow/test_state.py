# 示例: 在项目根目录执行 pytest backend/test/workflow/test_state.py -sv
"""workflow/state.py 状态模型单元测试。"""

import pytest
from workflow.state import (
    CopilotState, Job, CandidateProfile, ProfileBasic, Material, Fact,
    ResumeContent, ResumeProfile, ResumeContentMeta, SectionItem, Education,
    RenderConfig, PageMargin, ResumeHtml, Gap, Question, InterviewQA,
    ConversationEvent, Meta, DirtyFlags, PendingAction, SectionRationale,
)


class TestCopilotStateDefaults:

    def test_default_state(self):
        state = CopilotState()
        assert state.session_id == ""
        assert state.job is None
        assert state.candidate_profile is None
        assert state.resume_content_json is None
        assert state.gaps == []
        assert state.questions_to_ask == []
        assert state.interview_qa == []
        assert state.conversation_events == []
        assert state.user_message == ""
        assert state.execution_plan == []
        assert state.section_rationales == []

    def test_state_with_session_id(self):
        state = CopilotState(session_id="test_session_001")
        assert state.session_id == "test_session_001"


class TestJobModel:

    def test_job_creation(self):
        job = Job(
            id="job_001",
            title="AIGC工程师",
            industry="互联网",
            tech_stack=["Python", "LangChain", "RAG"],
            keywords=["GenAI", "LLM"],
            hard_skills=["Python", "RAG"],
            soft_skills=["团队合作"],
            responsibilities=["开发LLM应用"],
        )
        assert job.title == "AIGC工程师"
        assert "Python" in job.tech_stack
        assert job.version == 1

    def test_job_serialization(self):
        job = Job(id="j1", title="test")
        data = job.model_dump()
        assert data["id"] == "j1"
        assert data["title"] == "test"
        restored = Job.model_validate(data)
        assert restored.id == "j1"


class TestCandidateProfile:

    def test_profile_creation(self):
        profile = CandidateProfile(
            profile_basic=ProfileBasic(
                name="林知遥",
                email="lin.zhiyou@example.test",
                phone="+86-13900001234",
                city="杭州",
                school="星海理工大学",
            ),
            materials=[
                Material(
                    material_id="mat_001",
                    type="message",
                    content="个人简介测试",
                    uploaded_at="2026-04-12T00:00:00",
                ),
            ],
            facts=[
                Fact(id="f1", type="skill", content="Python"),
                Fact(id="f2", type="skill", content="LangChain"),
            ],
        )
        assert profile.profile_basic.name == "林知遥"
        assert len(profile.materials) == 1
        assert len(profile.facts) == 2


class TestResumeContent:

    def test_resume_content_creation(self):
        content = ResumeContent(
            profile=ResumeProfile(
                name="林知遥",
                email="test@test.com",
                phone="123",
                city="杭州",
                education=[
                    Education(
                        id="edu_1",
                        school="星海理工大学",
                        major="控制工程",
                        degree="硕士",
                        start_date="2025-09",
                        end_date="2028-06",
                    ),
                ],
            ),
            summary="AI 方向研究生",
            skills=[
                SectionItem(id="s1", title="Python", content="熟练掌握 Python"),
            ],
            meta=ResumeContentMeta(target_role="AIGC工程师", version=1),
        )
        assert content.profile.name == "林知遥"
        assert len(content.profile.education) == 1
        assert len(content.skills) == 1
        assert content.meta.target_role == "AIGC工程师"


class TestRenderConfig:

    def test_default_render_config(self):
        config = RenderConfig()
        assert config.template_id == "default"
        assert config.font_size == 14
        assert config.line_height == 1.5
        assert config.page_margin.top == 24
        assert "profile" in config.section_order
        assert config.layout_mode == "single-column"

    def test_custom_render_config(self):
        config = RenderConfig(
            theme="dark",
            font_size=12,
            dense_mode=True,
            layout_mode="double-column",
        )
        assert config.theme == "dark"
        assert config.font_size == 12
        assert config.dense_mode is True
        assert config.layout_mode == "double-column"


class TestGapAndQuestion:

    def test_gap_creation(self):
        gap = Gap(
            id="gap_1",
            type="missing_skill",
            severity="high",
            description="缺少 RAG 相关经验",
        )
        assert gap.type == "missing_skill"
        assert gap.resolved is False

    def test_question_creation(self):
        q = Question(
            id="q_1",
            question="你有 RAG 项目经验吗？",
            reason="JD 要求 RAG 经验",
            target_field="projects",
            priority="high",
        )
        assert q.status == "pending"


class TestConversationEvent:

    def test_event_creation(self):
        event = ConversationEvent(
            event_id="evt_001",
            message_id="msg_001",
            intent="upload_jd",
            triggered_agents=["jd_agent", "content_agent"],
        )
        assert event.intent == "upload_jd"
        assert len(event.triggered_agents) == 2
        assert event.status == "success"


class TestSectionRationale:

    def test_section_rationale_creation(self):
        rationale = SectionRationale(
            agent="content_agent",
            section="简历内容",
            decision="突出 RAG 项目",
            reason="目标岗位强调 RAG 实战经验。",
            evidence=["RAG"],
        )
        assert rationale.agent == "content_agent"
        assert rationale.section == "简历内容"
        assert rationale.status == "success"


class TestMeta:

    def test_dirty_flags_default(self):
        meta = Meta()
        assert meta.dirty_flags.content_dirty is False
        assert meta.dirty_flags.render_dirty is False

    def test_dirty_flags_update(self):
        meta = Meta()
        updated = meta.model_copy(update={
            "dirty_flags": meta.dirty_flags.model_copy(update={"content_dirty": True})
        })
        assert updated.dirty_flags.content_dirty is True
        assert updated.dirty_flags.render_dirty is False


class TestStateRoundTrip:
    """测试完整状态序列化/反序列化往返。"""

    def test_full_state_roundtrip(self):
        state = CopilotState(
            session_id="sess_test",
            job=Job(id="j1", title="测试岗位", tech_stack=["Python"]),
            candidate_profile=CandidateProfile(
                profile_basic=ProfileBasic(name="测试用户"),
            ),
            user_message="测试消息",
            current_intent="upload_jd",
            execution_plan=["jd_agent"],
        )
        data = state.model_dump()
        restored = CopilotState.model_validate(data)
        assert restored.session_id == "sess_test"
        assert restored.job.title == "测试岗位"
        assert restored.candidate_profile.profile_basic.name == "测试用户"
