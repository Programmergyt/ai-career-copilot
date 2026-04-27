"""Profile Agent — 解析用户材料，输出结构化 CandidateProfile。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from agents.json_contracts import ProfileExtractionOutput
from models.llm import get_llm, ainvoke_json_with_schema
from prompts.profile_extraction import PROFILE_EXTRACTION_PROMPT
from workflow.state import (
    CopilotState, CandidateProfile, ProfileBasic, Material, Fact,
)
from workflow.trace import append_trace, summarize_user_message
from log import get_logger

logger = get_logger("agent")


async def profile_node_async(state: CopilotState) -> dict[str, Any]:
    """Profile Agent 异步节点函数。"""
    logger.info("Profile Agent started for session %s", state.session_id)

    material_text = state.user_message
    now = datetime.now(timezone.utc).isoformat()
    material_id = f"mat_{uuid.uuid4().hex[:12]}"

    # 已有画像
    existing = state.candidate_profile
    existing_json = existing.model_dump_json(indent=2) if existing else "{}"

    prompt = PROFILE_EXTRACTION_PROMPT.format(
        material_text=material_text,
        existing_profile=existing_json,
    )
    llm = get_llm()
    try:
        parsed = await ainvoke_json_with_schema(llm, prompt, ProfileExtractionOutput, logger, "Profile Agent")
    except RuntimeError as exc:
        logger.error("Profile Agent failed: %s", exc)
        return {
            "workflow_trace": append_trace(
                state,
                node="profile_agent",
                status="failed",
                input_summary=f"解析候选人材料：{summarize_user_message(material_text)}",
                output_summary="候选人画像解析失败：模型输出格式异常，请重试。",
                error=str(exc),
            ),
        }

    # 构建 profile
    basic_data = parsed.profile_basic
    new_basic = ProfileBasic(
        name=basic_data.name,
        email=basic_data.email,
        phone=basic_data.phone,
        city=basic_data.city,
        school=basic_data.school,
    )

    # 增量合并 basic
    if existing:
        if not new_basic.name and existing.profile_basic.name:
            new_basic.name = existing.profile_basic.name
        if not new_basic.email and existing.profile_basic.email:
            new_basic.email = existing.profile_basic.email
        if not new_basic.phone and existing.profile_basic.phone:
            new_basic.phone = existing.profile_basic.phone
        if not new_basic.city and existing.profile_basic.city:
            new_basic.city = existing.profile_basic.city
        if not new_basic.school and existing.profile_basic.school:
            new_basic.school = existing.profile_basic.school

    # 新材料
    new_material = Material(
        material_id=material_id,
        type="message",
        content=material_text,
        uploaded_at=now,
    )

    # 合并材料
    materials = list(existing.materials) if existing else []
    materials.append(new_material)

    # 合并事实
    existing_facts = list(existing.facts) if existing else []
    new_facts_data = parsed.facts
    for fd in new_facts_data:
        fact = Fact(
            id=fd.id or f"fact_{uuid.uuid4().hex[:8]}",
            type=fd.type,
            content=fd.content,
            source_refs=fd.source_refs or [material_id],
            updated_at=now,
        )
        # 检查是否已存在相同 id 的事实，如果有则更新
        found = False
        for i, ef in enumerate(existing_facts):
            if ef.id == fact.id:
                existing_facts[i] = fact
                found = True
                break
        if not found:
            existing_facts.append(fact)

    profile = CandidateProfile(
        profile_basic=new_basic,
        materials=materials,
        facts=existing_facts,
    )

    logger.info("Profile updated: %s, %d facts", new_basic.name, len(existing_facts))

    meta = state.meta.model_copy(update={
        "dirty_flags": state.meta.dirty_flags.model_copy(update={
            "content_dirty": True,
            "render_dirty": True,
            "interview_dirty": True,
        })
    })

    return {
        "candidate_profile": profile,
        "meta": meta,
        "workflow_trace": append_trace(
            state,
            node="profile_agent",
            input_summary=f"解析候选人材料：{summarize_user_message(material_text)}",
            output_summary=f"已更新候选人画像：{new_basic.name or '未命名候选人'}，共 {len(existing_facts)} 条事实记录。",
            artifacts={
                "candidate_name": new_basic.name,
                "material_count": len(materials),
                "fact_count": len(existing_facts),
            },
        ),
    }


def profile_node(state: CopilotState) -> dict[str, Any]:
    """Profile Agent 同步兼容入口。"""
    return asyncio.run(profile_node_async(state))
