# 示例: 在项目根目录执行 pytest backend/test/workflow/test_workflow_graph.py -sv
"""workflow/graph.py 图结构与路由测试（不调用 LLM）。"""

import pytest
from workflow.graph import build_graph, _route_after_planner, _route_after_jd, _route_after_gap, _route_after_content, _route_after_render, _respond
from workflow.state import CopilotState, WorkflowTraceItem


class TestRouting:

    def test_route_after_planner_empty_plan(self):
        state = CopilotState(execution_plan=[])
        assert _route_after_planner(state) == "respond"

    def test_route_after_planner_jd(self):
        state = CopilotState(execution_plan=["jd_agent", "content_agent"])
        assert _route_after_planner(state) == "jd_agent"

    def test_route_after_planner_profile(self):
        state = CopilotState(execution_plan=["profile_agent"])
        assert _route_after_planner(state) == "profile_agent"

    def test_route_after_planner_render(self):
        state = CopilotState(execution_plan=["render_agent"])
        assert _route_after_planner(state) == "render_agent"

    def test_route_after_planner_question(self):
        state = CopilotState(execution_plan=["question_agent"])
        assert _route_after_planner(state) == "question_agent"

    def test_route_after_jd_to_gap(self):
        state = CopilotState(execution_plan=["jd_agent", "gap_agent"])
        assert _route_after_jd(state) == "gap_agent"

    def test_route_after_jd_to_content(self):
        state = CopilotState(execution_plan=["jd_agent", "content_agent"])
        assert _route_after_jd(state) == "content_agent"

    def test_route_after_jd_to_respond(self):
        state = CopilotState(execution_plan=["jd_agent"])
        assert _route_after_jd(state) == "respond"

    def test_route_after_content_to_render(self):
        state = CopilotState(execution_plan=["content_agent", "render_agent"])
        assert _route_after_content(state) == "render_agent"

    def test_route_after_content_to_respond(self):
        state = CopilotState(execution_plan=["content_agent"])
        assert _route_after_content(state) == "respond"

    def test_route_after_render_to_interview(self):
        state = CopilotState(execution_plan=["render_agent", "interview_agent"])
        assert _route_after_render(state) == "interview_agent"

    def test_route_after_render_to_respond(self):
        state = CopilotState(execution_plan=["render_agent"])
        assert _route_after_render(state) == "respond"


class TestRespondNode:

    def test_respond_with_empty_trace(self):
        state = CopilotState()
        result = _respond(state)
        assert "已完成本轮处理" in result["reply_message"]
        assert "没有可展示的节点记录" in result["reply_message"]

    def test_respond_builds_trace_reply(self):
        state = CopilotState(
            user_message="请分析岗位差距",
            current_intent="gap_analysis",
            execution_plan=["gap_agent"],
            workflow_trace=[
                WorkflowTraceItem(
                    node="planner",
                    output_summary="识别意图为 gap_analysis，执行计划为 gap_agent。",
                ),
                WorkflowTraceItem(
                    node="gap_agent",
                    output_summary="缺失信息分析已完成，发现 1 项缺口，生成 1 个待追问问题。",
                    artifacts={"gap_count": 1, "question_count": 1},
                ),
            ],
        )
        result = _respond(state)
        assert "用户输入：请分析岗位差距" in result["reply_message"]
        assert "意图识别：gap_analysis" in result["reply_message"]
        assert "执行计划：gap_agent" in result["reply_message"]
        assert "gap_agent [success]" in result["reply_message"]
        assert "缺失信息分析已完成" in result["reply_message"]


class TestBuildGraph:

    def test_build_graph_returns_stategraph(self):
        graph = build_graph()
        assert graph is not None

    def test_build_graph_has_expected_nodes(self):
        graph = build_graph()
        node_names = set(graph.nodes.keys())
        expected = {"planner", "jd_agent", "profile_agent", "gap_agent", "content_agent", "render_agent", "interview_agent", "question_agent", "respond"}
        assert expected.issubset(node_names)
