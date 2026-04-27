"""Runtime workflow trace helpers.

The trace is used to build the final user-facing reply for the current graph
run. It is intentionally excluded from persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from workflow.state import CopilotState, WorkflowTraceItem


def append_trace(
    state: CopilotState,
    *,
    node: str,
    status: str = "success",
    input_summary: str = "",
    output_summary: str = "",
    artifacts: dict[str, Any] | None = None,
    error: str = "",
) -> list[WorkflowTraceItem]:
    """Return the current trace plus one new item."""
    item = WorkflowTraceItem(
        node=node,
        status=status,
        input_summary=input_summary,
        output_summary=output_summary,
        artifacts=artifacts or {},
        error=error,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return [*state.workflow_trace, item]


def summarize_user_message(message: str, *, limit: int = 120) -> str:
    """Compact a user message for trace output."""
    text = " ".join((message or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."
