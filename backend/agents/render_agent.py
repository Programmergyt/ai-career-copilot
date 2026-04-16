"""Resume Render Agent — 渲染配置更新 + HTML 生成。"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from models.llm import get_llm, parse_json_response
from prompts.render_instruction import RENDER_INSTRUCTION_PROMPT
from tools.template_renderer import render_resume_html
from workflow.state import CopilotState, RenderConfig, ResumeHtml, PageMargin
from log import get_logger

logger = get_logger("agent")


def _update_render_config_from_llm(state: CopilotState) -> RenderConfig:
    """通过 LLM 解析渲染指令并更新配置。"""
    prompt = RENDER_INSTRUCTION_PROMPT.format(
        current_render_config=state.render_config.model_dump_json(indent=2),
        render_instruction=state.user_message,
    )
    llm = get_llm()
    response = llm.invoke(prompt)
    content = getattr(response, "content", str(response))
    parsed = parse_json_response(content)

    margin_data = parsed.get("page_margin", {})
    new_config = RenderConfig(
        template_id=parsed.get("template_id", state.render_config.template_id),
        theme=parsed.get("theme", state.render_config.theme),
        font_family=parsed.get("font_family", state.render_config.font_family),
        font_size=parsed.get("font_size", state.render_config.font_size),
        line_height=parsed.get("line_height", state.render_config.line_height),
        page_margin=PageMargin(
            top=margin_data.get("top", state.render_config.page_margin.top),
            right=margin_data.get("right", state.render_config.page_margin.right),
            bottom=margin_data.get("bottom", state.render_config.page_margin.bottom),
            left=margin_data.get("left", state.render_config.page_margin.left),
        ),
        section_order=parsed.get("section_order", state.render_config.section_order),
        dense_mode=parsed.get("dense_mode", state.render_config.dense_mode),
        accent_style=parsed.get("accent_style", state.render_config.accent_style),
        visibility_map=parsed.get("visibility_map", state.render_config.visibility_map),
        layout_mode=parsed.get("layout_mode", state.render_config.layout_mode),
        spacing_scale=parsed.get("spacing_scale", state.render_config.spacing_scale),
        version=state.render_config.version + 1,
        last_render_reason=parsed.get("last_render_reason", state.user_message),
    )
    return new_config


def render_node(state: CopilotState) -> dict[str, Any]:
    """Resume Render Agent 节点函数。"""
    logger.info("Resume Render Agent started for session %s", state.session_id)

    intent = state.current_intent
    render_config = state.render_config

    # 渲染指令 → 先更新 render_config
    if intent == "render_edit":
        render_config = _update_render_config_from_llm(state)
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
            "reply_message": "暂无简历内容，无法渲染。",
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
        "reply_message": msg,
    }
