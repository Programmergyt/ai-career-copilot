"""Tests for Planner Stage A: ENABLE_LLM_PLAN switch and fallback behavior."""

from __future__ import annotations

import asyncio

from agents.json_contracts import IntentClassificationOutput
from agents.registry import AgentRegistry
from agents.planner import planner_node_async
from workflow.plan_mode.plan_schema import Plan, PlanPolicy, PlanStep
from workflow.state import CopilotState


def _registry() -> AgentRegistry:
    registry = AgentRegistry()

    async def _ok_executor(state):
        return {"reply_message": "ok"}

    registry.register("question_answer_agent", _ok_executor)
    return registry


def _rule_plan() -> Plan:
    return Plan(
        plan_id="plan_rule",
        intent="ask_question",
        intent_bundle=["ask_question"],
        policy=PlanPolicy(),
        steps=[
            PlanStep(
                step_id="st_1",
                agent="question_answer_agent",
                action="answer_question",
                intent="ask_question",
                reads=[
                    "job",
                    "candidate_profile",
                    "resume_content_json",
                    "gaps",
                    "questions_to_ask",
                    "interview_qa",
                    "active_step",
                    "user_message",
                    "meta",
                ],
                writes=["reply_message"],
            )
        ],
    )


def _llm_plan() -> Plan:
    return Plan(
        plan_id="plan_llm",
        intent="ask_question",
        intent_bundle=["ask_question"],
        policy=PlanPolicy(),
        steps=[
            PlanStep(
                step_id="st_1",
                agent="question_answer_agent",
                action="answer_question",
                intent="ask_question",
                reads=[
                    "job",
                    "candidate_profile",
                    "resume_content_json",
                    "gaps",
                    "questions_to_ask",
                    "interview_qa",
                    "active_step",
                    "user_message",
                    "meta",
                ],
                writes=["reply_message"],
            )
        ],
    )


def test_planner_uses_rule_plan_when_switch_off(monkeypatch):
    monkeypatch.setattr("agents.planner.get_default_registry", lambda: _registry())
    monkeypatch.setattr("agents.planner.is_llm_plan_enabled", lambda: False)

    async def _resolve_intent(state: CopilotState):
        return IntentClassificationOutput(intent="ask_question", reason="test")

    monkeypatch.setattr("agents.planner._resolve_intent_async", _resolve_intent)
    monkeypatch.setattr("agents.planner._build_plan_with_rules", lambda state, primary_intent, task_bundle: _rule_plan())

    result = asyncio.run(planner_node_async(CopilotState(session_id="sess_rule", user_message="你好")))

    assert result["active_plan_id"] == "plan_rule"
    assert result["triggered_agents"] == ["question_answer_agent"]


def test_planner_uses_llm_plan_when_switch_on(monkeypatch):
    monkeypatch.setattr("agents.planner.get_default_registry", lambda: _registry())
    monkeypatch.setattr("agents.planner.is_llm_plan_enabled", lambda: True)

    async def _resolve_intent(state: CopilotState):
        return IntentClassificationOutput(intent="ask_question", reason="test")

    async def _build_llm_plan(state: CopilotState, primary_intent: str, task_bundle: list[str]):
        return _llm_plan()

    monkeypatch.setattr("agents.planner._resolve_intent_async", _resolve_intent)
    monkeypatch.setattr("agents.planner._build_plan_with_llm_async", _build_llm_plan)

    result = asyncio.run(planner_node_async(CopilotState(session_id="sess_llm", user_message="你好")))

    assert result["active_plan_id"] == "plan_llm"
    assert result["triggered_agents"] == ["question_answer_agent"]


def test_planner_falls_back_to_rule_plan_when_llm_plan_fails(monkeypatch):
    monkeypatch.setattr("agents.planner.get_default_registry", lambda: _registry())
    monkeypatch.setattr("agents.planner.is_llm_plan_enabled", lambda: True)

    async def _resolve_intent(state: CopilotState):
        return IntentClassificationOutput(intent="ask_question", reason="test")

    async def _build_llm_plan(state: CopilotState, primary_intent: str, task_bundle: list[str]):
        raise RuntimeError("llm plan failed")

    monkeypatch.setattr("agents.planner._resolve_intent_async", _resolve_intent)
    monkeypatch.setattr("agents.planner._build_plan_with_llm_async", _build_llm_plan)
    monkeypatch.setattr("agents.planner._build_plan_with_rules", lambda state, primary_intent, task_bundle: _rule_plan())

    result = asyncio.run(planner_node_async(CopilotState(session_id="sess_fallback", user_message="你好")))

    assert result["active_plan_id"] == "plan_rule"
    assert result["triggered_agents"] == ["question_answer_agent"]


def test_planner_falls_back_to_rule_plan_when_llm_plan_invalid(monkeypatch):
    monkeypatch.setattr("agents.planner.get_default_registry", lambda: _registry())
    monkeypatch.setattr("agents.planner.is_llm_plan_enabled", lambda: True)

    async def _resolve_intent(state: CopilotState):
        return IntentClassificationOutput(intent="ask_question", reason="test")

    async def _build_llm_plan(state: CopilotState, primary_intent: str, task_bundle: list[str]):
        return Plan(
            plan_id="plan_invalid",
            intent="ask_question",
            intent_bundle=["ask_question"],
            policy=PlanPolicy(),
            steps=[
                PlanStep(
                    step_id="st_1",
                    agent="question_answer_agent",
                    action="answer_question",
                    intent="ask_question",
                    reads=["user_message"],
                    writes=["resume_html"],
                )
            ],
        )

    monkeypatch.setattr("agents.planner._resolve_intent_async", _resolve_intent)
    monkeypatch.setattr("agents.planner._build_plan_with_llm_async", _build_llm_plan)
    monkeypatch.setattr("agents.planner._build_plan_with_rules", lambda state, primary_intent, task_bundle: _rule_plan())

    result = asyncio.run(planner_node_async(CopilotState(session_id="sess_invalid", user_message="你好")))

    assert result["active_plan_id"] == "plan_rule"
    assert result["triggered_agents"] == ["question_answer_agent"]
