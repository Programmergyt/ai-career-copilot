"""Agent contracts for runtime validation and registry metadata."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentContract:
    """Declares an agent's supported intents and state read/write boundaries."""

    name: str
    allowed_reads: frozenset[str]
    allowed_writes: frozenset[str]
    supported_intents: frozenset[str] = field(default_factory=frozenset)
    supported_actions: frozenset[str] = field(default_factory=frozenset)
    default_retryable: bool = False
    idempotent: bool = False


def _fs(*items: str) -> frozenset[str]:
    return frozenset(items)


AGENT_CONTRACTS: dict[str, AgentContract] = {
    "planner": AgentContract(
        name="planner",
        allowed_reads=_fs(
            "session_id",
            "job",
            "candidate_profile",
            "resume_content_json",
            "render_config",
            "gaps",
            "questions_to_ask",
            "interview_qa",
            "meta",
            "user_message",
            "user_attachments",
            "intent_bundle",
        ),
        allowed_writes=_fs(
            "active_plan_id",
            "plan_status",
            "current_intent",
            "intent_bundle",
            "execution_plan",
            "execution_steps",
            "plan_policy",
            "last_plan_error",
            "replan_candidate",
            "triggered_agents",
            "reply_message",
            "meta",
        ),
        supported_intents=_fs(
            "upload_jd",
            "upload_profile",
            "content_edit",
            "render_edit",
            "export",
            "ask_question",
        ),
    ),
    "jd_agent": AgentContract(
        name="jd_agent",
        allowed_reads=_fs("user_message", "user_attachments", "job", "meta"),
        allowed_writes=_fs("job", "meta", "reply_message"),
        supported_intents=_fs("upload_jd"),
        supported_actions=_fs("parse_job"),
    ),
    "profile_agent": AgentContract(
        name="profile_agent",
        allowed_reads=_fs("user_message", "user_attachments", "candidate_profile", "meta"),
        allowed_writes=_fs("candidate_profile", "meta", "reply_message"),
        supported_intents=_fs("upload_profile"),
        supported_actions=_fs("extract_profile"),
    ),
    "gap_agent": AgentContract(
        name="gap_agent",
        allowed_reads=_fs("job", "candidate_profile", "resume_content_json", "questions_to_ask", "meta", "active_step"),
        allowed_writes=_fs("gaps", "questions_to_ask", "meta", "reply_message"),
        supported_intents=_fs("upload_jd", "ask_question"),
        supported_actions=_fs("analyze_gap"),
        default_retryable=True,
    ),
    "content_agent": AgentContract(
        name="content_agent",
        allowed_reads=_fs(
            "job",
            "candidate_profile",
            "gaps",
            "resume_content_json",
            "current_intent",
            "active_step",
            "user_message",
            "meta",
        ),
        allowed_writes=_fs("resume_content_json", "meta", "reply_message"),
        supported_intents=_fs("upload_jd", "upload_profile", "content_edit"),
        supported_actions=_fs("generate_resume_content", "update_resume_content"),
        default_retryable=True,
    ),
    "render_agent": AgentContract(
        name="render_agent",
        allowed_reads=_fs(
            "resume_content_json",
            "render_config",
            "current_intent",
            "active_step",
            "user_message",
            "resume_html",
            "meta",
        ),
        allowed_writes=_fs("render_config", "resume_html", "meta", "reply_message"),
        supported_intents=_fs("render_edit", "upload_jd", "upload_profile", "content_edit"),
        supported_actions=_fs("render_resume", "update_render_config"),
        idempotent=True,
    ),
    "interview_agent": AgentContract(
        name="interview_agent",
        allowed_reads=_fs("job", "candidate_profile", "resume_content_json", "interview_qa", "meta", "active_step"),
        allowed_writes=_fs("interview_qa", "meta", "reply_message"),
        supported_intents=_fs("upload_jd", "upload_profile"),
        supported_actions=_fs("generate_interview_qa"),
        default_retryable=True,
    ),
}


def get_agent_contract(agent_name: str) -> AgentContract:
    """Look up a declared contract by agent name."""

    try:
        return AGENT_CONTRACTS[agent_name]
    except KeyError as exc:
        raise KeyError(f"Unknown agent contract: {agent_name}") from exc
