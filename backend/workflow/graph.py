"""LangGraph 图定义与编排。

MVP 阶段一：
  Planner → (JD Agent | Profile Agent) → Resume Content Agent → Resume Render Agent
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import StateGraph, END

from workflow.state import CopilotState
from agents.planner import planner_node
from agents.jd_agent import jd_node
from agents.profile_agent import profile_node
from agents.gap_agent import gap_node
from agents.content_agent import content_node
from agents.render_agent import render_node
from agents.interview_agent import interview_node
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
    """最终响应节点 — 收集结果。"""
    if not state.reply_message:
        return {"reply_message": "已处理完成。"}
    return {}


def build_graph() -> StateGraph:
    """构建主 workflow 图。"""
    graph = StateGraph(CopilotState)

    # 添加节点
    graph.add_node("planner", planner_node)
    graph.add_node("jd_agent", jd_node)
    graph.add_node("profile_agent", profile_node)
    graph.add_node("gap_agent", gap_node)
    graph.add_node("content_agent", content_node)
    graph.add_node("render_agent", render_node)
    graph.add_node("interview_agent", interview_node)
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

    # Respond → END
    graph.add_edge("respond", END)

    return graph


def compile_graph():
    """编译并返回可执行图。"""
    g = build_graph()
    return g.compile()
