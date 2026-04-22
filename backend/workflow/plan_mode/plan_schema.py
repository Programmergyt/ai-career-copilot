"""Plan Mode schema models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


PlanStatus = Literal["planned", "running", "success", "failed", "partial"]
StepStatus = Literal[
    "planned",
    "running",
    "success",
    "failed",
    "contract_violation",
    "skipped",
    "degraded_success",
]
RetryBackoff = Literal["none", "fixed_1s"]
PreconditionType = Literal["job_exists", "candidate_profile_exists", "resume_content_exists"]
StepOnError = Literal["fail", "skip", "degrade"]


class StepRetryPolicy(BaseModel):
    max_attempts: int = Field(default=1, ge=1, le=5)
    backoff: RetryBackoff = "none"


class StepPrecondition(BaseModel):
    kind: PreconditionType
    message: str = ""


class PlanStep(BaseModel):
    step_id: str
    agent: str
    action: str
    intent: str
    params: dict[str, Any] = Field(default_factory=dict)
    status: StepStatus = "planned"
    reads: list[str] = Field(default_factory=list)
    writes: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    preconditions: list[StepPrecondition] = Field(default_factory=list)
    retry: StepRetryPolicy = Field(default_factory=StepRetryPolicy)
    on_error: StepOnError = "fail"
    skippable: bool = False
    fallback_action: str = ""
    reason: str = ""


class PlanPolicy(BaseModel):
    fail_fast: bool = True
    partial_success: bool = False
    allow_degraded_completion: bool = False


class Plan(BaseModel):
    plan_id: str
    intent: str
    intent_bundle: list[str] = Field(default_factory=list)
    steps: list[PlanStep] = Field(default_factory=list)
    policy: PlanPolicy = Field(default_factory=PlanPolicy)


class StepResult(BaseModel):
    step_id: str
    agent: str
    action: str
    status: StepStatus
    attempt: int = 1
    latency_ms: int = 0
    writes: list[str] = Field(default_factory=list)
    error_code: str = ""
    error: str = ""
    degraded: bool = False
    skipped: bool = False


class ContractViolation(BaseModel):
    step_id: str
    agent: str
    action: str
    field: str
    reason: str
