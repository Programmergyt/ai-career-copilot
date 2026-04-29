"""User-facing rationale helpers for the current graph run."""

from __future__ import annotations

from typing import Any

from workflow.state import CopilotState, SectionRationale


def summarize_user_message(message: str, *, limit: int = 120) -> str:
    """Compact a user message for user-facing status text."""
    text = " ".join((message or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def append_section_rationales(
    state: CopilotState,
    *,
    agent: str,
    rationales: list[Any] | None = None,
    fallback_section: str = "",
    fallback_decision: str = "",
    fallback_reason: str = "",
    fallback_evidence: list[str] | None = None,
    status: str = "success",
) -> list[SectionRationale]:
    """Return current rationales plus normalized user-facing rationales."""
    new_items: list[SectionRationale] = []
    for item in rationales or []:
        if isinstance(item, SectionRationale):
            data = item.model_dump()
        elif hasattr(item, "model_dump"):
            data = item.model_dump()
        elif isinstance(item, dict):
            data = item
        else:
            continue

        rationale = SectionRationale(
            agent=agent,
            section=str(data.get("section") or fallback_section or agent),
            decision=str(data.get("decision") or fallback_decision),
            reason=str(data.get("reason") or fallback_reason),
            evidence=[str(value) for value in (data.get("evidence") or [])],
            status=str(data.get("status") or status),
        )
        if rationale.decision or rationale.reason:
            new_items.append(rationale)

    if not new_items and (fallback_decision or fallback_reason):
        new_items.append(SectionRationale(
            agent=agent,
            section=fallback_section or agent,
            decision=fallback_decision,
            reason=fallback_reason,
            evidence=fallback_evidence or [],
            status=status,
        ))

    return [*state.section_rationales, *new_items]
