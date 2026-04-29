"""Memory extraction unit tests."""

from __future__ import annotations

from memory.contracts import MemoryKind
from memory.extractor import MemoryExtractor
from workflow.state import CandidateProfile, CopilotState, Fact, ProfileBasic


def test_extracts_new_profile_fact_memory():
    final_state = CopilotState(
        session_id="sess_memory_test",
        candidate_profile=CandidateProfile(
            profile_basic=ProfileBasic(name="测试用户"),
            facts=[
                Fact(
                    id="fact_skill_python",
                    type="skill",
                    content="Python 和 RAG 项目经验",
                    source_refs=["mat_1"],
                )
            ],
        ),
    )

    records = MemoryExtractor().extract(
        old_state=CopilotState(session_id="sess_memory_test"),
        final_state=final_state,
        user_message="补充我的技能",
    )

    assert len(records) == 1
    assert records[0].kind == MemoryKind.PROFILE_FACT.value
    assert records[0].session_id == "sess_memory_test"
    assert "Python" in records[0].content


def test_extracts_explicit_preference_memory():
    final_state = CopilotState(session_id="sess_memory_pref")

    records = MemoryExtractor().extract(
        old_state=None,
        final_state=final_state,
        user_message="请记住以后默认使用单页紧凑简历。",
    )

    preference_records = [record for record in records if record.kind == MemoryKind.PREFERENCE.value]
    assert len(preference_records) == 1
    assert "单页紧凑" in preference_records[0].content
