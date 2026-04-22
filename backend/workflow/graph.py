"""LangGraph definition for serial Plan Mode."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from agents.runtime import make_runtime_node
from log import get_logger
from workflow.plan_mode.plan_executor import plan_executor_node_async
from workflow.state import CopilotState

logger = get_logger("agent")


def _respond(state: CopilotState) -> dict[str, Any]:
    """Final response node."""
    if not state.reply_message:
        return {"reply_message": "已处理完成。"}
    return {}


def build_graph() -> StateGraph:
    """Build the plan-mode workflow graph."""
    graph = StateGraph(CopilotState)
    graph.add_node("planner", make_runtime_node("planner"))
    graph.add_node("executor", plan_executor_node_async)
    graph.add_node("respond", _respond)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "respond")
    graph.add_edge("respond", END)
    return graph


def compile_graph():
    """Compile and return the executable graph."""
    return build_graph().compile()
