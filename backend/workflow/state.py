"""LangGraph State 定义 — 全局状态 Schema。

所有 Agent 共享该状态结构，通过 LangGraph State 管理。
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


# ---- 子结构 ----

class ProfileBasic(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    school: str = ""


class Material(BaseModel):
    material_id: str
    type: str  # pdf / docx / text / message
    content: str
    uploaded_at: str


class Fact(BaseModel):
    id: str
    type: str  # skill / project / internship / award / paper
    content: str
    source_refs: list[str] = Field(default_factory=list)
    updated_at: str = ""


class CandidateProfile(BaseModel):
    profile_basic: ProfileBasic = Field(default_factory=ProfileBasic)
    materials: list[Material] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)


class Education(BaseModel):
    id: str
    school: str
    major: str
    degree: str
    start_date: str
    end_date: str


class ResumeProfile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    github: str = ""
    education: list[Education] = Field(default_factory=list)


class SectionItem(BaseModel):
    id: str
    title: str
    content: str
    source_refs: list[str] = Field(default_factory=list)
    updated_at: str = ""


class ResumeContentMeta(BaseModel):
    target_role: str = ""
    version: int = 1
    last_updated_at: str = ""
    content_hash: str = ""


class ResumeContent(BaseModel):
    profile: ResumeProfile = Field(default_factory=ResumeProfile)
    summary: str = ""
    skills: list[SectionItem] = Field(default_factory=list)
    internships: list[SectionItem] = Field(default_factory=list)
    projects: list[SectionItem] = Field(default_factory=list)
    awards: list[SectionItem] = Field(default_factory=list)
    papers: list[SectionItem] = Field(default_factory=list)
    meta: ResumeContentMeta = Field(default_factory=ResumeContentMeta)


class PageMargin(BaseModel):
    top: int = 24
    right: int = 24
    bottom: int = 24
    left: int = 24


class RenderConfig(BaseModel):
    template_id: str = "default"
    theme: str = "light"
    font_family: str = "Source Han Sans"
    font_size: int = 14
    line_height: float = 1.5
    page_margin: PageMargin = Field(default_factory=PageMargin)
    section_order: list[str] = Field(
        default_factory=lambda: ["profile", "skills", "projects", "internships", "awards"]
    )
    dense_mode: bool = False
    accent_style: str = "minimal"
    visibility_map: dict[str, bool] = Field(default_factory=dict)
    layout_mode: str = "single-column"
    spacing_scale: str = "standard"
    version: int = 1
    last_render_reason: str = ""


class ResumeHtml(BaseModel):
    html: str = ""
    version: int = 1
    derived_from_content_version: int = 0
    derived_from_render_version: int = 0
    updated_at: str = ""
    checksum: str = ""


class Gap(BaseModel):
    id: str
    type: str  # missing_skill / missing_experience / no_quantification / low_relevance
    severity: str  # high / medium / low
    description: str
    related_section_ids: list[str] = Field(default_factory=list)
    resolved: bool = False
    resolution_source: str = ""


class Question(BaseModel):
    id: str
    question: str
    reason: str
    target_field: str
    priority: str  # high / medium / low
    status: str = "pending"  # pending / answered / dismissed
    answer_ref: str = ""


class InterviewQA(BaseModel):
    id: str
    category: str  # technical / project_deep_dive / behavioral
    question: str
    answer: str
    source_refs: list[str] = Field(default_factory=list)
    version: int = 1


class ConversationEvent(BaseModel):
    event_id: str
    message_id: str
    intent: str
    triggered_agents: list[str] = Field(default_factory=list)
    state_diff_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
    status: str = "success"


class WorkflowTraceItem(BaseModel):
    node: str
    status: str = "success"  # success / skipped / failed
    input_summary: str = ""
    output_summary: str = ""
    artifacts: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    created_at: str = ""


class DirtyFlags(BaseModel):
    content_dirty: bool = False
    render_dirty: bool = False
    interview_dirty: bool = False
    export_dirty: bool = False


class Meta(BaseModel):
    active_resume_content_version: int = 0
    active_render_version: int = 0
    active_html_version: int = 0
    last_user_message_id: str = ""
    last_successful_pipeline: str = ""
    dirty_flags: DirtyFlags = Field(default_factory=DirtyFlags)


class PendingAction(BaseModel):
    id: str
    type: str  # wait_answer / export / render_confirm / async_generate
    status: str = "pending"
    owner_agent: str = ""
    depends_on: list[str] = Field(default_factory=list)
    created_at: str = ""


class Job(BaseModel):
    id: str = ""
    source: str = ""
    parsed_at: str = ""
    version: int = 1
    industry: str = ""
    title: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    hard_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    education_requirement: str = ""
    experience_requirement: str = ""
    implicit_preferences: list[str] = Field(default_factory=list)
    bonus_items: list[str] = Field(default_factory=list)


# ---- 顶层 State ----

class CopilotState(BaseModel):
    """LangGraph 全局状态。"""
    session_id: str = ""
    job: Optional[Job] = None
    candidate_profile: Optional[CandidateProfile] = None
    resume_content_json: Optional[ResumeContent] = None
    render_config: RenderConfig = Field(default_factory=RenderConfig)
    resume_html: ResumeHtml = Field(default_factory=ResumeHtml)
    gaps: list[Gap] = Field(default_factory=list)
    questions_to_ask: list[Question] = Field(default_factory=list)
    interview_qa: list[InterviewQA] = Field(default_factory=list)
    conversation_events: list[ConversationEvent] = Field(default_factory=list)
    meta: Meta = Field(default_factory=Meta)
    pending_actions: list[PendingAction] = Field(default_factory=list)

    # ---- 运行时字段（不持久化）----
    user_message: str = ""
    user_attachments: list[dict[str, Any]] = Field(default_factory=list)
    current_intent: str = ""
    execution_plan: list[str] = Field(default_factory=list)
    reply_message: str = ""
    triggered_agents: list[str] = Field(default_factory=list)
    workflow_trace: list[WorkflowTraceItem] = Field(default_factory=list)
