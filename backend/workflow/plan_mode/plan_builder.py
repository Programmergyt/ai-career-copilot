"""Dynamic plan builder for Plan Mode."""

from __future__ import annotations

from dataclasses import dataclass, field
import uuid

from workflow.plan_mode.plan_schema import Plan, PlanPolicy, PlanStep, StepPrecondition, StepRetryPolicy
from workflow.state import CopilotState


TASK_PRIORITY = {
    "upload_jd": 10,
    "upload_profile": 20,
    "content_edit": 30,
    "render_edit": 40,
    "gap_analysis": 50,
    "ask_question": 60,
}


@dataclass
class _StepSpec:
    key: str
    agent: str
    action: str
    intent: str
    reads: list[str]
    writes: list[str]
    depends_on: list[str] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    retry_attempts: int = 1
    params: dict = field(default_factory=dict)
    on_error: str = "fail"
    skippable: bool = False
    fallback_action: str = ""
    reason: str = ""


def _make_step(plan_id: str, index: int, spec: _StepSpec, id_by_key: dict[str, str]) -> PlanStep:
    return PlanStep(
        step_id=f"{plan_id}_st_{index:02d}",
        agent=spec.agent,
        action=spec.action,
        intent=spec.intent,
        params=spec.params,
        reads=spec.reads,
        writes=spec.writes,
        depends_on=[id_by_key[key] for key in spec.depends_on if key in id_by_key],
        preconditions=[StepPrecondition(kind=kind) for kind in spec.preconditions],
        retry=StepRetryPolicy(
            max_attempts=spec.retry_attempts,
            backoff="fixed_1s" if spec.retry_attempts > 1 else "none",
        ),
        on_error=spec.on_error,
        skippable=spec.skippable,
        fallback_action=spec.fallback_action,
        reason=spec.reason,
    )


def _normalize_tasks(tasks: list[str]) -> list[str]:
    return sorted(dict.fromkeys(tasks), key=lambda item: TASK_PRIORITY.get(item, 999))


def _has_future_job(state: CopilotState, tasks: list[str]) -> bool:
    return state.job is not None or "upload_jd" in tasks


def _has_future_profile(state: CopilotState, tasks: list[str]) -> bool:
    return state.candidate_profile is not None or "upload_profile" in tasks


def _add_upload_jd_specs(specs: list[_StepSpec], state: CopilotState, tasks: list[str]) -> None:
    specs.append(_StepSpec(
        key="jd.parse",
        agent="jd_agent",
        action="parse_job",
        intent="upload_jd",
        reads=["user_message", "user_attachments", "job"],
        writes=["job"],
        reason="解析最新岗位描述并写入结构化 job。",
    ))
    if not _has_future_profile(state, tasks):
        return

    gap_depends = ["jd.parse"]
    if "upload_profile" in tasks:
        gap_depends.append("profile.extract")

    specs.extend([
        _StepSpec(
            key="gap.refresh",
            agent="gap_agent",
            action="analyze_gap",
            intent="upload_jd",
            reads=["job", "candidate_profile", "resume_content_json"],
            writes=["gaps", "questions_to_ask"],
            depends_on=gap_depends,
            preconditions=["job_exists", "candidate_profile_exists"],
            retry_attempts=2,
            params={"mode": "refresh"},
            on_error="degrade",
            skippable=True,
            fallback_action="skip_gap_refresh",
            reason="基于最新岗位和候选人画像生成缺口分析。",
        ),
        _StepSpec(
            key="content.generate",
            agent="content_agent",
            action="generate_resume_content",
            intent="upload_jd",
            reads=["job", "candidate_profile", "gaps", "resume_content_json", "user_message"],
            writes=["resume_content_json"],
            depends_on=gap_depends,
            preconditions=["job_exists", "candidate_profile_exists"],
            retry_attempts=2,
            params={"mode": "generate"},
            reason="基于岗位和候选人画像生成简历内容。",
        ),
        _StepSpec(
            key="render.refresh",
            agent="render_agent",
            action="render_resume",
            intent="upload_jd",
            reads=["resume_content_json", "render_config", "resume_html"],
            writes=["render_config", "resume_html"],
            depends_on=["content.generate"],
            preconditions=["resume_content_exists"],
            params={"mode": "refresh"},
            reason="渲染最新简历内容。",
        ),
        _StepSpec(
            key="interview.generate",
            agent="interview_agent",
            action="generate_interview_qa",
            intent="upload_jd",
            reads=["job", "candidate_profile", "resume_content_json", "interview_qa"],
            writes=["interview_qa"],
            depends_on=["content.generate"],
            preconditions=["job_exists", "candidate_profile_exists", "resume_content_exists"],
            retry_attempts=2,
            on_error="degrade",
            skippable=True,
            fallback_action="skip_interview_generation",
            reason="基于岗位和简历内容生成面试问答。",
        ),
    ])


def _add_upload_profile_specs(specs: list[_StepSpec], state: CopilotState, tasks: list[str]) -> None:
    specs.append(_StepSpec(
        key="profile.extract",
        agent="profile_agent",
        action="extract_profile",
        intent="upload_profile",
        reads=["user_message", "user_attachments", "candidate_profile"],
        writes=["candidate_profile"],
        reason="解析并更新候选人画像。",
    ))

    if "upload_jd" in tasks:
        return

    specs.append(_StepSpec(
        key="content.generate",
        agent="content_agent",
        action="generate_resume_content",
        intent="upload_profile",
        reads=["job", "candidate_profile", "gaps", "resume_content_json", "user_message"],
        writes=["resume_content_json"],
        depends_on=["profile.extract"],
        preconditions=["candidate_profile_exists"],
        retry_attempts=2,
        params={"mode": "generate"},
        reason="基于候选人画像生成或刷新简历内容。",
    ))
    specs.append(_StepSpec(
        key="render.refresh",
        agent="render_agent",
        action="render_resume",
        intent="upload_profile",
        reads=["resume_content_json", "render_config", "resume_html"],
        writes=["render_config", "resume_html"],
        depends_on=["content.generate"],
        preconditions=["resume_content_exists"],
        params={"mode": "refresh"},
        reason="渲染当前简历内容。",
    ))
    if _has_future_job(state, tasks):
        specs.append(_StepSpec(
            key="interview.generate",
            agent="interview_agent",
            action="generate_interview_qa",
            intent="upload_profile",
            reads=["job", "candidate_profile", "resume_content_json", "interview_qa"],
            writes=["interview_qa"],
            depends_on=["content.generate"],
            preconditions=["job_exists", "candidate_profile_exists", "resume_content_exists"],
            retry_attempts=2,
            on_error="degrade",
            skippable=True,
            fallback_action="skip_interview_generation",
            reason="在岗位已存在时生成面试问答。",
        ))


def _add_content_edit_specs(specs: list[_StepSpec], tasks: list[str], state: CopilotState) -> None:
    specs.append(_StepSpec(
        key="content.edit",
        agent="content_agent",
        action="update_resume_content",
        intent="content_edit",
        reads=["resume_content_json", "job", "candidate_profile", "gaps", "user_message"],
        writes=["resume_content_json"],
        preconditions=["resume_content_exists"],
        retry_attempts=2,
        params={"mode": "edit", "instruction": state.user_message},
        reason="基于用户编辑指令更新简历内容。",
    ))
    if "render_edit" not in tasks:
        specs.append(_StepSpec(
            key="render.refresh.after_content",
            agent="render_agent",
            action="render_resume",
            intent="content_edit",
            reads=["resume_content_json", "render_config", "resume_html"],
            writes=["render_config", "resume_html"],
            depends_on=["content.edit"],
            preconditions=["resume_content_exists"],
            params={"mode": "refresh", "reason": "内容编辑后刷新渲染"},
            reason="渲染内容编辑后的简历。",
        ))


def _add_render_edit_specs(specs: list[_StepSpec], tasks: list[str], state: CopilotState) -> None:
    depends_on: list[str] = []
    if "content_edit" in tasks:
        depends_on.append("content.edit")

    specs.append(_StepSpec(
        key="render.edit",
        agent="render_agent",
        action="update_render_config",
        intent="render_edit",
        reads=["resume_content_json", "render_config", "resume_html", "user_message"],
        writes=["render_config", "resume_html"],
        depends_on=depends_on,
        preconditions=["resume_content_exists"],
        params={"mode": "edit", "instruction": state.user_message},
        reason="根据渲染指令更新配置并重新渲染。",
    ))


def _add_ask_question_specs(specs: list[_StepSpec]) -> None:
    specs.append(_StepSpec(
        key="qa.answer",
        agent="question_answer_agent",
        action="answer_question",
        intent="ask_question",
        reads=["job", "candidate_profile", "resume_content_json", "gaps", "questions_to_ask", "interview_qa", "user_message"],
        writes=["reply_message"],
        retry_attempts=2,
        params={"mode": "qa"},
        reason="基于当前已加载状态回答用户问题。",
    ))


def _add_gap_analysis_specs(specs: list[_StepSpec]) -> None:
    specs.append(_StepSpec(
        key="gap.ask",
        agent="gap_agent",
        action="analyze_gap",
        intent="gap_analysis",
        reads=["job", "candidate_profile", "resume_content_json"],
        writes=["gaps", "questions_to_ask"],
        preconditions=["job_exists", "candidate_profile_exists"],
        retry_attempts=2,
        params={"mode": "ask"},
        reason="围绕岗位与候选人画像生成缺口分析和追问。",
    ))


def build_plan_from_tasks(tasks: list[str], state: CopilotState, *, primary_intent: str | None = None) -> Plan:
    """Build a dynamic Plan from a task bundle."""
    normalized_tasks = _normalize_tasks(tasks)
    plan_id = f"plan_{uuid.uuid4().hex[:12]}"
    specs: list[_StepSpec] = []

    for task in normalized_tasks:
        if task == "upload_jd":
            _add_upload_jd_specs(specs, state, normalized_tasks)
        elif task == "upload_profile":
            _add_upload_profile_specs(specs, state, normalized_tasks)
        elif task == "content_edit":
            _add_content_edit_specs(specs, normalized_tasks, state)
        elif task == "render_edit":
            _add_render_edit_specs(specs, normalized_tasks, state)
        elif task == "gap_analysis":
            _add_gap_analysis_specs(specs)
        elif task == "ask_question":
            _add_ask_question_specs(specs)

    deduped_specs: list[_StepSpec] = []
    by_key: dict[str, _StepSpec] = {}
    for spec in specs:
        existing = by_key.get(spec.key)
        if existing is None:
            by_key[spec.key] = spec
            deduped_specs.append(spec)
            continue
        existing.depends_on = list(dict.fromkeys([*existing.depends_on, *spec.depends_on]))
        existing.preconditions = list(dict.fromkeys([*existing.preconditions, *spec.preconditions]))
        if spec.reason and not existing.reason:
            existing.reason = spec.reason

    id_by_key = {
        spec.key: f"{plan_id}_st_{index:02d}"
        for index, spec in enumerate(deduped_specs, start=1)
    }
    steps = [
        _make_step(plan_id, index, spec, id_by_key)
        for index, spec in enumerate(deduped_specs, start=1)
    ]

    return Plan(
        plan_id=plan_id,
        intent=primary_intent or (normalized_tasks[0] if normalized_tasks else "ask_question"),
        intent_bundle=normalized_tasks,
        steps=steps,
        policy=PlanPolicy(
            fail_fast=True,
            partial_success=True,
            allow_degraded_completion=True,
        ),
    )
