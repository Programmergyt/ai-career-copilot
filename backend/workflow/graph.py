"""LangGraph 图定义与编排。

MVP 阶段一：
  Planner → (JD Agent | Profile Agent) → Resume Content Agent → Resume Render Agent
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import StateGraph, END

from workflow.state import CopilotState
from workflow.rationales import summarize_user_message
from agents.planner import planner_node_async
from agents.jd_agent import jd_node_async
from agents.profile_agent import profile_node_async
from agents.gap_agent import gap_node_async
from agents.content_agent import content_node_async
from agents.render_agent import render_node_async
from agents.interview_agent import interview_node_async
from agents.question_agent import question_node_async
from log import get_logger

logger = get_logger("agent")


def _route_after_planner(state: CopilotState) -> str:
    """根据 Planner 识别的 intent 路由到下一个节点。"""
    plan = state.execution_plan
    if not plan:
        return "respond"
    return plan[0]


def _route_after_jd(state: CopilotState) -> str:
    plan = state.execution_plan
    if "gap_agent" in plan:
        return "gap_agent"
    if "content_agent" in plan:
        return "content_agent"
    return "respond"


def _route_after_profile(state: CopilotState) -> str:
    plan = state.execution_plan
    if "content_agent" in plan:
        return "content_agent"
    return "respond"


def _route_after_gap(state: CopilotState) -> str:
    plan = state.execution_plan
    if "content_agent" in plan:
        return "content_agent"
    return "respond"


def _route_after_content(state: CopilotState) -> str:
    plan = state.execution_plan
    if "render_agent" in plan:
        return "render_agent"
    return "respond"


def _route_after_render(state: CopilotState) -> str:
    plan = state.execution_plan
    if "interview_agent" in plan:
        return "interview_agent"
    return "respond"


def _respond(state: CopilotState) -> dict[str, Any]:
    """最终响应节点 — 将 agent rationale 汇总为用户可读 Markdown。"""
    return {"reply_message": _build_markdown_reply(state)}


def _build_markdown_reply(state: CopilotState) -> str:
    lines = ["已完成这轮处理。"]

    if state.user_message or state.current_intent:
        lines.extend([
            "",
            "### 我理解的需求",
            f"- 你的输入：{summarize_user_message(state.user_message) or '空'}",
            f"- 我把它识别为：{state.current_intent or '未识别'}",
        ])

    if state.current_intent == "ask_question" and state.agent_reply_message:
        lines.extend(["", "### 回答", state.agent_reply_message])

    lines.extend(["", "### 我为什么这样处理"])
    if state.section_rationales:
        for item in state.section_rationales:
            prefix = f"**{item.section or item.agent or '处理说明'}**"
            text = item.decision or "完成相关处理"
            if item.reason:
                text = f"{text}。{item.reason}"
            if item.status == "failed":
                text = f"{text}（处理失败）"
            elif item.status == "skipped":
                text = f"{text}（已跳过）"
            lines.append(f"- {prefix}：{text}")
            if item.evidence:
                evidence = "；".join(str(value) for value in item.evidence[:3] if value)
                if evidence:
                    lines.append(f"  依据：{evidence}")
    else:
        lines.append("- 这轮没有需要展开解释的生成决策。")

    final_result = _final_result_summary(state)
    lines.extend(["", "### 处理结果", final_result])
    return "\n".join(lines)


def _final_result_summary(state: CopilotState) -> str:
    failed = [item for item in state.section_rationales if item.status == "failed"]
    if failed:
        return failed[-1].reason or "本轮处理未完成，请检查失败节点。"

    if state.current_intent == "ask_question" and state.agent_reply_message:
        return "问题已回答。"

    if state.current_intent == "export":
        return "导出功能将在后续版本中支持。"

    parts: list[str] = []
    if state.job and state.job.title:
        parts.append(f"目标岗位：{state.job.title}")
    if state.resume_content_json:
        parts.append(f"简历内容 v{state.resume_content_json.meta.version} 已准备")
    if state.resume_html.html:
        parts.append(f"简历预览 v{state.resume_html.version} 已渲染")
    if state.gaps:
        parts.append(f"发现 {len(state.gaps)} 项能力缺口")
    if state.questions_to_ask:
        parts.append(f"整理 {len(state.questions_to_ask)} 个待补充问题")
    if state.interview_qa:
        parts.append(f"生成 {len(state.interview_qa)} 条面试问答")

    if parts:
        return "；".join(parts) + "。"
    return "本轮处理已完成。"


def build_graph() -> StateGraph:
    """构建主 workflow 图。"""
    graph = StateGraph(CopilotState)

    # 添加节点
    graph.add_node("planner", planner_node_async)
    graph.add_node("jd_agent", jd_node_async)
    graph.add_node("profile_agent", profile_node_async)
    graph.add_node("gap_agent", gap_node_async)
    graph.add_node("content_agent", content_node_async)
    graph.add_node("render_agent", render_node_async)
    graph.add_node("interview_agent", interview_node_async)
    graph.add_node("question_agent", question_node_async)
    graph.add_node("respond", _respond)

    # 入口
    graph.set_entry_point("planner")

    # Planner 路由
    graph.add_conditional_edges("planner", _route_after_planner, {
        "jd_agent": "jd_agent",
        "profile_agent": "profile_agent",
        "gap_agent": "gap_agent",
        "content_agent": "content_agent",
        "render_agent": "render_agent",
        "interview_agent": "interview_agent",
        "question_agent": "question_agent",
        "respond": "respond",
    })

    # JD Agent → Content or Respond
    graph.add_conditional_edges("jd_agent", _route_after_jd, {
        "gap_agent": "gap_agent",
        "content_agent": "content_agent",
        "respond": "respond",
    })

    # Profile Agent → Content or Respond
    graph.add_conditional_edges("profile_agent", _route_after_profile, {
        "content_agent": "content_agent",
        "respond": "respond",
    })

    # Gap Agent → Content or Respond
    graph.add_conditional_edges("gap_agent", _route_after_gap, {
        "content_agent": "content_agent",
        "respond": "respond",
    })

    # Content Agent → Render or Respond
    graph.add_conditional_edges("content_agent", _route_after_content, {
        "render_agent": "render_agent",
        "respond": "respond",
    })

    # Render Agent → Interview or Respond
    graph.add_conditional_edges("render_agent", _route_after_render, {
        "interview_agent": "interview_agent",
        "respond": "respond",
    })

    # Interview Agent → Respond
    graph.add_edge("interview_agent", "respond")

    # Question Agent → Respond
    graph.add_edge("question_agent", "respond")

    # Respond → END
    graph.add_edge("respond", END)

    return graph


def compile_graph():
    """编译并返回可执行图。"""
    g = build_graph()
    return g.compile()
