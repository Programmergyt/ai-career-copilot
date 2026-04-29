"""Resume Render Agent — 渲染配置更新 + HTML 生成。"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any

from agents.json_contracts import RenderInstructionOutput
from models.llm import get_llm, ainvoke_json_with_schema
from prompts.render_instruction import RENDER_INSTRUCTION_PROMPT
from tools.template_renderer import render_resume_html
from workflow.state import CopilotState, RenderConfig, ResumeHtml, PageMargin
from workflow.rationales import append_section_rationales, summarize_user_message
from log import get_logger

logger = get_logger("agent")


async def _update_render_config_from_llm_async(state: CopilotState) -> tuple[RenderConfig, Any]:
    """异步解析渲染指令并更新配置。"""
    prompt = RENDER_INSTRUCTION_PROMPT.format(
        current_render_config=state.render_config.model_dump_json(indent=2),
        render_instruction=state.user_message,
    )
    llm = get_llm()
    parsed = await ainvoke_json_with_schema(llm, prompt, RenderInstructionOutput, logger, "Resume Render Agent")

    margin_data = parsed.page_margin
    new_config = RenderConfig(
        template_id=parsed.template_id or state.render_config.template_id,
        theme=parsed.theme or state.render_config.theme,
        font_family=parsed.font_family or state.render_config.font_family,
        font_size=parsed.font_size,
        line_height=parsed.line_height,
        page_margin=PageMargin(
            top=margin_data.top,
            right=margin_data.right,
            bottom=margin_data.bottom,
            left=margin_data.left,
        ),
        section_order=parsed.section_order or state.render_config.section_order,
        dense_mode=parsed.dense_mode,
        accent_style=parsed.accent_style or state.render_config.accent_style,
        visibility_map=parsed.visibility_map or state.render_config.visibility_map,
        layout_mode=parsed.layout_mode or state.render_config.layout_mode,
        spacing_scale=parsed.spacing_scale or state.render_config.spacing_scale,
        version=state.render_config.version + 1,
        last_render_reason=parsed.last_render_reason or state.user_message,
    )
    return new_config, parsed


async def render_node_async(state: CopilotState) -> dict[str, Any]:
    """Resume Render Agent 异步节点函数。"""
    logger.info("Resume Render Agent started for session %s", state.session_id)

    intent = state.current_intent
    render_config = state.render_config

    # 渲染指令 → 先更新 render_config
    render_parsed = None
    if intent == "render_edit":
        try:
            render_config, render_parsed = await _update_render_config_from_llm_async(state)
        except RuntimeError as exc:
            logger.error("Resume Render Agent failed: %s", exc)
            return {
                "section_rationales": append_section_rationales(
                    state,
                    agent="render_agent",
                    status="failed",
                    fallback_section="视觉呈现",
                    fallback_decision="暂时无法解析渲染指令",
                    fallback_reason="模型返回的渲染配置不符合 JSON 约束，请重试或换一种样式描述。",
                    fallback_evidence=[summarize_user_message(state.user_message)],
                ),
            }
        logger.info("Render config updated to v%d", render_config.version)
    else:
        # 内容更新触发，只递增版本
        render_config = render_config.model_copy(update={
            "version": render_config.version + 1,
            "last_render_reason": "内容更新触发渲染",
        })

    # 生成 HTML
    resume_content = state.resume_content_json
    if resume_content is None:
        return {
            "render_config": render_config,
            "section_rationales": append_section_rationales(
                state,
                agent="render_agent",
                status="skipped",
                fallback_section="视觉呈现",
                fallback_decision="暂不渲染简历",
                fallback_reason="渲染需要先有简历内容，目前还没有可生成 HTML 的内容。",
                fallback_evidence=[summarize_user_message(state.user_message)],
            ),
        }

    html_str = render_resume_html(resume_content, render_config)
    checksum = hashlib.sha256(html_str.encode()).hexdigest()[:16]

    resume_html = ResumeHtml(
        html=html_str,
        version=state.resume_html.version + 1,
        derived_from_content_version=resume_content.meta.version,
        derived_from_render_version=render_config.version,
        updated_at=datetime.now(timezone.utc).isoformat(),
        checksum=checksum,
    )

    logger.info("HTML rendered v%d (checksum=%s)", resume_html.version, checksum)

    meta = state.meta.model_copy(update={
        "active_render_version": render_config.version,
        "active_html_version": resume_html.version,
        "dirty_flags": state.meta.dirty_flags.model_copy(update={
            "render_dirty": False,
            "export_dirty": True,
        })
    })

    msg = "简历已渲染。"
    if intent == "render_edit":
        msg = f"渲染配置已更新，简历已重新渲染（v{resume_html.version}）。"

    return {
        "render_config": render_config,
        "resume_html": resume_html,
        "meta": meta,
        "section_rationales": append_section_rationales(
            state,
            agent="render_agent",
            rationales=render_parsed.section_rationales if render_parsed else [],
            fallback_section="视觉呈现",
            fallback_decision=msg,
            fallback_reason="渲染配置会把已生成的简历内容转换为可预览的 HTML，并尽量保持版式与用户要求一致。",
            fallback_evidence=[
                f"layout_mode={render_config.layout_mode}",
                f"template_id={render_config.template_id}",
            ],
        ),
    }


def render_node(state: CopilotState) -> dict[str, Any]:
    """Resume Render Agent 同步兼容入口。"""
    return asyncio.run(render_node_async(state))
