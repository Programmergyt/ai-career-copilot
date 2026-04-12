"""Resume Content Agent — 生成/更新 resume_content_json。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from models.llm import get_llm, parse_json_response
from prompts.resume_generation import RESUME_GENERATION_PROMPT, RESUME_SECTION_UPDATE_PROMPT
from workflow.state import (
    CopilotState, ResumeContent, ResumeProfile, ResumeContentMeta,
    SectionItem, Education,
)
from log import get_logger

logger = get_logger("agent")


def _build_resume_from_parsed(parsed: dict, state: CopilotState) -> ResumeContent:
    """从 LLM 返回的 JSON 构建 ResumeContent 对象。"""
    now = datetime.now(timezone.utc).isoformat()

    profile_data = parsed.get("profile", {})
    education_list = []
    for ed in profile_data.get("education", []):
        education_list.append(Education(
            id=ed.get("id", ""),
            school=ed.get("school", ""),
            major=ed.get("major", ""),
            degree=ed.get("degree", ""),
            start_date=ed.get("start_date", ""),
            end_date=ed.get("end_date", ""),
        ))

    resume_profile = ResumeProfile(
        name=profile_data.get("name", ""),
        email=profile_data.get("email", ""),
        phone=profile_data.get("phone", ""),
        city=profile_data.get("city", ""),
        github=profile_data.get("github", ""),
        education=education_list,
    )

    def _parse_items(items: list[dict]) -> list[SectionItem]:
        return [SectionItem(
            id=item.get("id", ""),
            title=item.get("title", ""),
            content=item.get("content", ""),
            source_refs=item.get("source_refs", []),
            updated_at=now,
        ) for item in items]

    content_json = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
    content_hash = hashlib.sha256(content_json.encode()).hexdigest()[:16]

    version = 1
    if state.resume_content_json:
        version = state.resume_content_json.meta.version + 1

    target_role = ""
    if state.job:
        target_role = state.job.title

    return ResumeContent(
        profile=resume_profile,
        summary=parsed.get("summary", ""),
        skills=_parse_items(parsed.get("skills", [])),
        internships=_parse_items(parsed.get("internships", [])),
        projects=_parse_items(parsed.get("projects", [])),
        awards=_parse_items(parsed.get("awards", [])),
        papers=_parse_items(parsed.get("papers", [])),
        meta=ResumeContentMeta(
            target_role=target_role,
            version=version,
            last_updated_at=now,
            content_hash=content_hash,
        ),
    )


def content_node(state: CopilotState) -> dict[str, Any]:
    """Resume Content Agent 节点函数。"""
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

    response = llm.invoke(prompt)
    content = getattr(response, "content", str(response))
    parsed = parse_json_response(content)

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
        "reply_message": f"简历内容已生成（v{resume_content.meta.version}）。",
    }
