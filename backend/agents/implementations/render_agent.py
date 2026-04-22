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
from log import get_logger

logger = get_logger("agent")


def _resolve_render_mode(state: CopilotState) -> tuple[str, str]:
    active_step = state.active_step
    if active_step is not None:
        mode = str(active_step.params.get("mode") or "").strip().lower()
        instruction = str(active_step.params.get("instruction") or state.user_message)
        if active_step.action == "update_render_config" or mode == "edit":
            return "edit", instruction
        return "refresh", instruction

    if state.current_intent == "render_edit":
        return "edit", state.user_message
    return "refresh", state.user_message


async def _update_render_config_from_llm_async(state: CopilotState, instruction: str) -> RenderConfig:
    """异步解析渲染指令并更新配置。"""
    prompt = RENDER_INSTRUCTION_PROMPT.format(
        current_render_config=state.render_config.model_dump_json(indent=2),
        render_instruction=instruction,
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
        last_render_reason=parsed.last_render_reason or instruction,
    )
    return new_config


async def render_node_async(state: CopilotState) -> dict[str, Any]:
    """Resume Render Agent 异步节点函数。"""
    logger.info("Resume Render Agent started for session %s", state.session_id)

    mode, instruction = _resolve_render_mode(state)
    render_config = state.render_config

    if mode == "edit":
        try:
            render_config = await _update_render_config_from_llm_async(state, instruction)
        except RuntimeError as exc:
            logger.error("Resume Render Agent failed: %s", exc)
            return {
                "reply_message": "渲染配置解析失败：模型输出格式异常，请重试。",
            }
        logger.info("Render config updated to v%d", render_config.version)
    else:
        render_config = render_config.model_copy(update={
            "version": render_config.version + 1,
            "last_render_reason": "内容更新触发渲染",
        })

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
    if mode == "edit":
        msg = f"渲染配置已更新，简历已重新渲染（v{resume_html.version}）。"

    return {
        "render_config": render_config,
        "resume_html": resume_html,
        "meta": meta,
        "reply_message": msg,
    }


def render_node(state: CopilotState) -> dict[str, Any]:
    """Resume Render Agent 同步兼容入口。"""
    return asyncio.run(render_node_async(state))
