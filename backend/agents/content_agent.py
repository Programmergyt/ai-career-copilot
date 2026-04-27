"""Resume Content Agent — 生成/更新 resume_content_json。"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from agents.json_contracts import ResumeGenerationOutput
from models.llm import get_llm, ainvoke_json_with_schema
from prompts.resume_generation import RESUME_GENERATION_PROMPT, RESUME_SECTION_UPDATE_PROMPT
from workflow.state import (
    CopilotState, ResumeContent, ResumeProfile, ResumeContentMeta,
    SectionItem, Education,
)
from workflow.trace import append_trace, summarize_user_message
from log import get_logger

logger = get_logger("agent")


def _build_resume_from_parsed(parsed: ResumeGenerationOutput, state: CopilotState) -> ResumeContent:
    """从 LLM 返回的 JSON 构建 ResumeContent 对象。"""
    now = datetime.now(timezone.utc).isoformat()

    profile_data = parsed.profile
    education_list = []
    for ed in profile_data.education:
        education_list.append(Education(
            id=ed.id,
            school=ed.school,
            major=ed.major,
            degree=ed.degree,
            start_date=ed.start_date,
            end_date=ed.end_date,
        ))

    resume_profile = ResumeProfile(
        name=profile_data.name,
        email=profile_data.email,
        phone=profile_data.phone,
        city=profile_data.city,
        github=profile_data.github,
        education=education_list,
    )

    def _parse_items(items: list[Any]) -> list[SectionItem]:
        return [SectionItem(
            id=item.id,
            title=item.title,
            content=item.content,
            source_refs=item.source_refs,
            updated_at=now,
        ) for item in items]

    content_json = json.dumps(parsed.model_dump(), ensure_ascii=False, sort_keys=True)
    content_hash = hashlib.sha256(content_json.encode()).hexdigest()[:16]

    version = 1
    if state.resume_content_json:
        version = state.resume_content_json.meta.version + 1

    target_role = ""
    if state.job:
        target_role = state.job.title

    return ResumeContent(
        profile=resume_profile,
        summary=parsed.summary,
        skills=_parse_items(parsed.skills),
        internships=_parse_items(parsed.internships),
        projects=_parse_items(parsed.projects),
        awards=_parse_items(parsed.awards),
        papers=_parse_items(parsed.papers),
        meta=ResumeContentMeta(
            target_role=target_role,
            version=version,
            last_updated_at=now,
            content_hash=content_hash,
        ),
    )


async def content_node_async(state: CopilotState) -> dict[str, Any]:
    """Resume Content Agent 异步节点函数。"""
    logger.info("Resume Content Agent started for session %s", state.session_id)

    intent = state.current_intent
    llm = get_llm()

    if intent == "content_edit" and state.resume_content_json:
        # 局部更新
        prompt = RESUME_SECTION_UPDATE_PROMPT.format(
            current_resume_json=state.resume_content_json.model_dump_json(indent=2),
            job_json=state.job.model_dump_json(indent=2) if state.job else "{}",
            edit_instruction=state.user_message,
        )
    else:
        # 全量生成
        job_json = state.job.model_dump_json(indent=2) if state.job else "{}"
        profile_json = state.candidate_profile.model_dump_json(indent=2) if state.candidate_profile else "{}"

        edit_instruction = ""
        if intent == "content_edit":
            edit_instruction = f"用户修改指令：{state.user_message}"

        prompt = RESUME_GENERATION_PROMPT.format(
            job_json=job_json,
            profile_json=profile_json,
            edit_instruction=edit_instruction,
        )

    try:
        parsed = await ainvoke_json_with_schema(llm, prompt, ResumeGenerationOutput, logger, "Resume Content Agent")
    except RuntimeError as exc:
        logger.error("Resume Content Agent failed: %s", exc)
        return {
            "workflow_trace": append_trace(
                state,
                node="content_agent",
                status="failed",
                input_summary=f"根据岗位、候选人画像和用户指令生成简历内容：{summarize_user_message(state.user_message)}",
                output_summary="简历内容生成失败：模型输出格式异常，请重试。",
                error=str(exc),
            ),
        }

    resume_content = _build_resume_from_parsed(parsed, state)

    logger.info("Resume content generated v%d, hash=%s",
                resume_content.meta.version, resume_content.meta.content_hash)

    meta = state.meta.model_copy(update={
        "active_resume_content_version": resume_content.meta.version,
        "dirty_flags": state.meta.dirty_flags.model_copy(update={
            "content_dirty": False,
            "render_dirty": True,
            "interview_dirty": True,
            "export_dirty": True,
        })
    })

    return {
        "resume_content_json": resume_content,
        "meta": meta,
        "workflow_trace": append_trace(
            state,
            node="content_agent",
            input_summary=f"根据岗位、候选人画像和用户指令生成简历内容：{summarize_user_message(state.user_message)}",
            output_summary=f"简历内容已生成（v{resume_content.meta.version}）。",
            artifacts={
                "resume_content_version": resume_content.meta.version,
                "target_role": resume_content.meta.target_role,
                "skill_count": len(resume_content.skills),
                "project_count": len(resume_content.projects),
                "internship_count": len(resume_content.internships),
                "content_hash": resume_content.meta.content_hash,
            },
        ),
    }


def content_node(state: CopilotState) -> dict[str, Any]:
    """Resume Content Agent 同步兼容入口。"""
    return asyncio.run(content_node_async(state))
