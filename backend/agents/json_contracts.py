"""Pydantic JSON contracts for agent machine-protocol outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IntentClassificationOutput(BaseModel):
    intent: str = "ask_question"
    reason: str = ""


class JDAnalysisOutput(BaseModel):
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


class ProfileBasicOutput(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    school: str = ""


class ProfileFactOutput(BaseModel):
    id: str = ""
    type: str = "skill"
    content: str = ""
    source_refs: list[str] = Field(default_factory=list)
    updated_at: str = ""


class ProfileExtractionOutput(BaseModel):
    profile_basic: ProfileBasicOutput = Field(default_factory=ProfileBasicOutput)
    facts: list[ProfileFactOutput] = Field(default_factory=list)


class GapOutput(BaseModel):
    id: str = ""
    type: str = "missing_skill"
    severity: str = "medium"
    description: str = ""
    related_section_ids: list[str] = Field(default_factory=list)
    resolved: bool = False
    resolution_source: str = "gap_analysis"


class QuestionOutput(BaseModel):
    id: str = ""
    question: str = ""
    reason: str = ""
    target_field: str = ""
    priority: str = "medium"
    status: str = "pending"
    answer_ref: str = ""


class GapAnalysisOutput(BaseModel):
    gaps: list[GapOutput] = Field(default_factory=list)
    questions_to_ask: list[QuestionOutput] = Field(default_factory=list)


class EducationOutput(BaseModel):
    id: str = ""
    school: str = ""
    major: str = ""
    degree: str = ""
    start_date: str = ""
    end_date: str = ""


class ResumeProfileOutput(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    github: str = ""
    education: list[EducationOutput] = Field(default_factory=list)


class ResumeSectionItemOutput(BaseModel):
    id: str = ""
    title: str = ""
    content: str = ""
    source_refs: list[str] = Field(default_factory=list)
    updated_at: str = ""


class ResumeGenerationOutput(BaseModel):
    profile: ResumeProfileOutput = Field(default_factory=ResumeProfileOutput)
    summary: str = ""
    skills: list[ResumeSectionItemOutput] = Field(default_factory=list)
    internships: list[ResumeSectionItemOutput] = Field(default_factory=list)
    projects: list[ResumeSectionItemOutput] = Field(default_factory=list)
    awards: list[ResumeSectionItemOutput] = Field(default_factory=list)
    papers: list[ResumeSectionItemOutput] = Field(default_factory=list)


class PageMarginOutput(BaseModel):
    top: int = 24
    right: int = 24
    bottom: int = 24
    left: int = 24


class RenderInstructionOutput(BaseModel):
    template_id: str = "default"
    theme: str = "light"
    font_family: str = "Source Han Sans"
    font_size: int = 14
    line_height: float = 1.5
    page_margin: PageMarginOutput = Field(default_factory=PageMarginOutput)
    section_order: list[str] = Field(default_factory=list)
    dense_mode: bool = False
    accent_style: str = "minimal"
    visibility_map: dict[str, bool] = Field(default_factory=dict)
    layout_mode: str = "single-column"
    spacing_scale: str = "standard"
    last_render_reason: str = ""


class InterviewQAOutput(BaseModel):
    id: str = ""
    category: str = "technical"
    question: str = ""
    answer: str = ""
    source_refs: list[str] = Field(default_factory=list)
    version: int = 1


class InterviewGenerationOutput(BaseModel):
    interview_qa: list[InterviewQAOutput] = Field(default_factory=list)