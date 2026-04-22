"""Task extraction helpers for dynamic Plan Mode."""

from __future__ import annotations

from collections.abc import Iterable

from workflow.state import CopilotState


SUPPORTED_TASKS = (
    "upload_jd",
    "upload_profile",
    "content_edit",
    "render_edit",
    "ask_question",
)

_CONTENT_EDIT_HINTS = (
    "简历",
    "内容",
    "润色",
    "改写",
    "改一下",
    "优化",
    "补充",
    "修改项目",
    "修改经历",
)
_RENDER_EDIT_HINTS = (
    "排版",
    "布局",
    "双栏",
    "双列",
    "字号",
    "字距",
    "行距",
    "字体",
    "模板",
    "渲染",
    "样式",
    "配色",
)


def _dedupe(items: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in SUPPORTED_TASKS and item not in seen:
            ordered.append(item)
            seen.add(item)
    return ordered


def extract_task_bundle(primary_intent: str, state: CopilotState) -> list[str]:
    """Return a normalized task bundle for the current turn."""
    if state.intent_bundle:
        return _dedupe(state.intent_bundle)

    message = state.user_message or ""
    has_content_hint = any(token in message for token in _CONTENT_EDIT_HINTS)
    has_render_hint = any(token in message for token in _RENDER_EDIT_HINTS)

    if primary_intent in {"upload_jd", "upload_profile", "ask_question"}:
        return [primary_intent]

    if primary_intent == "content_edit":
        tasks = ["content_edit"]
        if has_render_hint:
            tasks.append("render_edit")
        return _dedupe(tasks)

    if primary_intent == "render_edit":
        tasks: list[str] = []
        if has_content_hint:
            tasks.append("content_edit")
        tasks.append("render_edit")
        return _dedupe(tasks)

    return _dedupe([primary_intent or "ask_question"])
