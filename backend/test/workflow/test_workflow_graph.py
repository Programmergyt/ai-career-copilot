# 示例: 在项目根目录执行 pytest backend/test/workflow/test_workflow_graph.py -sv
"""workflow/graph.py graph shape tests for serial Plan Mode."""

import pytest

pytest.importorskip("langgraph")

from workflow.graph import build_graph, _respond
from workflow.state import CopilotState


class TestRespondNode:

    def test_respond_with_empty_reply(self):
        state = CopilotState()
        result = _respond(state)
        assert result["reply_message"] == "已处理完成。"

    def test_respond_with_existing_reply(self):
        state = CopilotState(reply_message="已解析岗位")
        result = _respond(state)
        assert result == {}


class TestBuildGraph:

    def test_build_graph_returns_stategraph(self):
        graph = build_graph()
        assert graph is not None

    def test_build_graph_has_expected_nodes(self):
        graph = build_graph()
        node_names = set(graph.nodes.keys())
        assert node_names == {"planner", "executor", "respond"}
