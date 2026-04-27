"""LangGraph 图定义与编排。

MVP 阶段一：
  Planner → (JD Agent | Profile Agent) → Resume Content Agent → Resume Render Agent
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import StateGraph, END

from workflow.state import CopilotState
from workflow.trace import summarize_user_message
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
    """最终响应节点 — 基于本轮运行轨迹生成稳定的过程记录。"""
    return {"reply_message": _build_trace_reply(state)}


def _format_artifacts(artifacts: dict[str, Any]) -> str:
    if not artifacts:
        return ""
    parts = []
    for key, value in artifacts.items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        parts.append(f"{key}={value}")
    return f"（{'; '.join(parts)}）" if parts else ""


def _build_trace_reply(state: CopilotState) -> str:
    plan_text = " -> ".join(state.execution_plan) if state.execution_plan else "无后续 Agent"
    lines = [
        "已完成本轮处理。",
        "",
        "**执行过程**",
        f"1. 用户输入：{summarize_user_message(state.user_message) or '空'}",
        f"2. 意图识别：{state.current_intent or '未识别'}",
        f"3. 执行计划：{plan_text}",
        "4. 节点产物：",
    ]

    if state.workflow_trace:
        for item in state.workflow_trace:
            artifacts = _format_artifacts(item.artifacts)
            status = item.status
            line = f"   - {item.node} [{status}]：{item.output_summary}{artifacts}"
            if item.error:
                line += f"；错误：{item.error}"
            lines.append(line)
    else:
        lines.append("   - respond [success]：没有可展示的节点记录。")

    final_result = _final_result_summary(state)
    lines.extend(["", "**最终结果**", final_result])
    return "\n".join(lines)


def _final_result_summary(state: CopilotState) -> str:
    if state.workflow_trace:
        failed = [item for item in state.workflow_trace if item.status == "failed"]
        if failed:
            return failed[-1].output_summary or "本轮处理未完成，请检查失败节点。"

        if state.current_intent == "ask_question":
            for item in reversed(state.workflow_trace):
                if item.node == "question_agent":
                    return item.output_summary or "问题已处理完成。"

        non_planner_items = [item for item in state.workflow_trace if item.node != "planner"]
        if non_planner_items:
            return non_planner_items[-1].output_summary or "本轮处理已完成。"

    if state.current_intent == "export":
        return "导出功能将在后续版本中支持。"
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
