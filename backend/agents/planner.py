"""Planner Agent — intent resolution + serial plan building + validation."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from agents.json_contracts import IntentClassificationOutput
from agents.plan_contracts import PlannerPlanOutput
from agents.registry import get_default_registry
from config_loader import is_llm_plan_enabled
from log import get_logger
from models.llm import ainvoke_json_with_schema, get_llm
from prompts.intent_classification import INTENT_CLASSIFICATION_PROMPT
from prompts.plan_generation import PLAN_GENERATION_PROMPT
from workflow.plan_mode.plan_builder import build_plan_from_tasks
from workflow.plan_mode.plan_schema import Plan, PlanPolicy, PlanStep, StepPrecondition, StepRetryPolicy
from workflow.plan_mode.task_extractor import extract_task_bundle
from workflow.plan_mode.plan_validator import PlanValidationError, validate_plan
from workflow.state import CopilotState

logger = get_logger("agent")


async def _classify_intent_async(state: CopilotState) -> IntentClassificationOutput:
    """Classify the user message into a supported workflow intent."""
    prompt = INTENT_CLASSIFICATION_PROMPT.format(
        has_job=state.job is not None,
        has_profile=state.candidate_profile is not None,
        has_resume=state.resume_content_json is not None,
        user_message=state.user_message,
    )
    llm = get_llm()
    result = await ainvoke_json_with_schema(llm, prompt, IntentClassificationOutput, logger, "Planner Agent")
    logger.info("Intent classified: %s (reason: %s)", result.intent, result.reason)
    return result


async def _resolve_intent_async(state: CopilotState) -> IntentClassificationOutput:
    """Honor an explicit current_intent override when internal APIs provide one."""
    if state.intent_bundle:
        logger.info("Planner task bundle override detected: %s", state.intent_bundle)
        return IntentClassificationOutput(
            intent=state.intent_bundle[0],
            reason="task bundle override from existing state",
        )
    if state.current_intent:
        logger.info("Planner intent override detected: %s", state.current_intent)
        return IntentClassificationOutput(
            intent=state.current_intent,
            reason="intent override from existing state",
        )
    return await _classify_intent_async(state)


def _build_agent_catalog() -> str:
    registry = get_default_registry()
    rows: list[str] = []
    for name in registry.names():
        contract = registry.get_contract(name)
        intents = ", ".join(sorted(contract.supported_intents)) or "<none>"
        actions = ", ".join(sorted(contract.supported_actions)) or "<any>"
        reads = ", ".join(sorted(contract.allowed_reads))
        writes = ", ".join(sorted(contract.allowed_writes))
        rows.append(
            f"- {name} | supported_intents=[{intents}] | supported_actions=[{actions}] | "
            f"allowed_reads=[{reads}] | allowed_writes=[{writes}]"
        )
    return "\n".join(rows)


def _convert_llm_plan_output(
    output: PlannerPlanOutput,
    *,
    primary_intent: str,
    fallback_bundle: list[str],
) -> Plan:
    plan_id = f"plan_{uuid.uuid4().hex[:12]}"
    key_to_step_id: dict[str, str] = {}
    for index, step in enumerate(output.steps, start=1):
        if step.key in key_to_step_id:
            raise ValueError(f"Duplicate step key in llm plan: {step.key}")
        key_to_step_id[step.key] = f"{plan_id}_st_{index:02d}"

    steps: list[PlanStep] = []
    for index, step in enumerate(output.steps, start=1):
        missing_dep = [dep for dep in step.depends_on if dep not in key_to_step_id]
        if missing_dep:
            raise ValueError(f"Step {step.key} depends on unknown keys: {', '.join(missing_dep)}")
        steps.append(
            PlanStep(
                step_id=f"{plan_id}_st_{index:02d}",
                agent=step.agent,
                action=step.action,
                intent=step.intent or primary_intent,
                reads=list(step.reads),
                writes=list(step.writes),
                depends_on=[key_to_step_id[dep] for dep in step.depends_on],
                preconditions=[StepPrecondition(kind=kind) for kind in step.preconditions],
                retry=StepRetryPolicy(
                    max_attempts=step.retry_max_attempts,
                    backoff="fixed_1s" if step.retry_max_attempts > 1 else "none",
                ),
                on_error=step.on_error,
                skippable=step.skippable,
                fallback_action=step.fallback_action,
                reason=step.reason,
            )
        )

    intent_bundle = list(dict.fromkeys(output.intent_bundle or fallback_bundle))
    if not intent_bundle:
        intent_bundle = [primary_intent]

    return Plan(
        plan_id=plan_id,
        intent=output.intent or primary_intent,
        intent_bundle=intent_bundle,
        steps=steps,
        policy=PlanPolicy(
            fail_fast=output.policy.fail_fast,
            partial_success=output.policy.partial_success,
            allow_degraded_completion=output.policy.allow_degraded_completion,
        ),
    )


async def _build_plan_with_llm_async(
    state: CopilotState,
    *,
    primary_intent: str,
    task_bundle: list[str],
) -> Plan:
    prompt = PLAN_GENERATION_PROMPT.format(
        primary_intent=primary_intent,
        task_bundle_json=json.dumps(task_bundle, ensure_ascii=False),
        has_job=state.job is not None,
        has_profile=state.candidate_profile is not None,
        has_resume=state.resume_content_json is not None,
        user_message=state.user_message,
        agent_catalog=_build_agent_catalog(),
    )
    llm = get_llm()
    parsed = await ainvoke_json_with_schema(llm, prompt, PlannerPlanOutput, logger, "Planner Plan Agent")
    return _convert_llm_plan_output(parsed, primary_intent=primary_intent, fallback_bundle=task_bundle)


def _build_plan_with_rules(state: CopilotState, *, primary_intent: str, task_bundle: list[str]) -> Plan:
    return build_plan_from_tasks(task_bundle, state, primary_intent=primary_intent)


async def planner_node_async(state: CopilotState) -> dict[str, Any]:
    """Planner Agent async node."""
    logger.info("Planner Agent started for session %s", state.session_id)

    try:
        intent_result = await _resolve_intent_async(state)
    except RuntimeError as exc:
        logger.error("Planner Agent failed: %s", exc)
        return {
            "active_plan_id": "",
            "plan_status": "failed",
            "current_intent": "ask_question",
            "execution_plan": [],
            "execution_steps": [],
            "triggered_agents": [],
            "reply_message": "意图识别失败：模型输出格式异常，请稍后重试。",
        }

    intent = intent_result.intent or "ask_question"
    task_bundle = extract_task_bundle(intent, state)
    registry = get_default_registry()

    try:
        plan_source = "rule"
        if is_llm_plan_enabled():
            try:
                plan = await _build_plan_with_llm_async(state, primary_intent=intent, task_bundle=task_bundle)
                validate_plan(plan, state, registry)
                plan_source = "llm"
            except (RuntimeError, ValueError, TypeError, KeyError, PlanValidationError) as exc:
                logger.warning("LLM plan generation failed, fallback to rule plan: %s", exc)
                plan = _build_plan_with_rules(state, primary_intent=intent, task_bundle=task_bundle)
                plan_source = "rule_fallback"
                validate_plan(plan, state, registry)
        else:
            plan = _build_plan_with_rules(state, primary_intent=intent, task_bundle=task_bundle)
            validate_plan(plan, state, registry)
        execution_plan = [step.agent for step in plan.steps]
    except PlanValidationError as exc:
        logger.error("Planner generated invalid plan: %s", exc)
        return {
            "active_plan_id": "",
            "plan_status": "failed",
            "current_intent": intent,
            "execution_plan": [],
            "execution_steps": [],
            "triggered_agents": [],
            "reply_message": f"计划生成失败：{exc}",
        }

    logger.info("Plan source: %s", plan_source)
    logger.info("Execution plan: %s", execution_plan)
    logger.info("Execution steps: %s", [step.agent for step in plan.steps])

    message_id = state.meta.last_user_message_id or f"msg_{uuid.uuid4().hex[:12]}"
    updates: dict[str, Any] = {
        "active_plan_id": plan.plan_id,
        "plan_status": "planned",
        "current_intent": intent,
        "intent_bundle": plan.intent_bundle,
        "execution_plan": execution_plan,
        "execution_steps": plan.steps,
        "plan_policy": plan.policy,
        "triggered_agents": list(execution_plan),
        "last_plan_error": "",
        "replan_candidate": False,
    }

    if not execution_plan:
        if intent == "export":
            updates["reply_message"] = "导出功能将在后续版本中支持。"
        elif intent == "ask_question":
            updates["reply_message"] = intent_result.reason or "请提供更多信息。"

    updates["meta"] = state.meta.model_copy(update={
        "last_user_message_id": message_id,
    })

    return updates


def planner_node(state: CopilotState) -> dict[str, Any]:
    """Planner Agent sync entry."""
    return asyncio.run(planner_node_async(state))
