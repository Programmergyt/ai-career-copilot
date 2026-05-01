"""Context window management tests."""

from __future__ import annotations

from memory.context_window import MemoryContextWindowManager
from memory.contracts import MemoryBundle, MemoryHit, MemoryRecord
from workflow.state import CopilotState


def test_context_window_trims_memory_and_user_message_under_budget():
    manager = MemoryContextWindowManager()
    manager._max_context_tokens = 2200
    manager._max_response_tokens = 200
    manager._safety_margin_tokens = 100
    manager._memory_context_tokens = 300
    manager._summary_tokens = 80
    manager._min_retrieval_tokens = 60

    record = MemoryRecord(
        memory_id="mem_1",
        session_id="sess_ctx",
        kind="profile_fact",
        content="memory detail " * 700,
    )
    bundle = MemoryBundle(
        hits=[MemoryHit(record=record, score=0.9)],
        summary="memory detail " * 700,
    )
    state = CopilotState(
        session_id="sess_ctx",
        user_message="user detail " * 1200,
        memory_context="memory detail " * 700,
        retrieved_memories=[{"memory_id": "mem_1"}],
    )

    result = manager.manage(state, bundle)

    assert result.stats.within_budget is True
    assert result.stats.estimated_tokens_after <= result.stats.budget_tokens
    assert result.stats.truncated_tokens > 0
    assert result.stats.memory_tokens_after <= result.stats.memory_tokens_before
