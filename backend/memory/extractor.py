"""Rule-based extraction from workflow state into memory records."""

from __future__ import annotations

from typing import Iterable

from memory.contracts import MemoryKind, MemoryRecord, MemoryScope, MemoryStatus
from memory.policy import build_memory_id, compact_text, content_hash, utc_now
from workflow.state import CopilotState, InterviewQA, Material, SectionItem


class MemoryExtractor:
    """Extracts durable memories without calling LLMs or touching workflow internals."""

    def extract(
        self,
        *,
        old_state: CopilotState | None,
        final_state: CopilotState,
        user_message: str,
        user_id: str | None = None,
    ) -> list[MemoryRecord]:
        records: list[MemoryRecord] = []
        records.extend(self._profile_fact_memories(old_state, final_state, user_id))
        records.extend(self._resume_artifact_memories(final_state, user_id))
        records.extend(self._material_artifact_memories(old_state, final_state, user_id))
        records.extend(self._interview_artifact_memories(final_state, user_id))

        preference = self._explicit_preference_memory(final_state, user_message, user_id)
        if preference:
            records.append(preference)

        return _dedupe(records)

    def _profile_fact_memories(
        self,
        old_state: CopilotState | None,
        final_state: CopilotState,
        user_id: str | None,
    ) -> list[MemoryRecord]:
        profile = final_state.candidate_profile
        if not profile:
            return []

        old_fact_hashes = set()
        if old_state and old_state.candidate_profile:
            old_fact_hashes = {
                f"{fact.id}:{content_hash(fact.content)}"
                for fact in old_state.candidate_profile.facts
            }

        records: list[MemoryRecord] = []
        for fact in profile.facts:
            fact_marker = f"{fact.id}:{content_hash(fact.content)}"
            if fact_marker in old_fact_hashes:
                continue
            content = compact_text(f"{fact.type}: {fact.content}")
            memory_id = build_memory_id(
                kind=MemoryKind.PROFILE_FACT,
                source_id=f"profile_fact:{fact.id}",
                user_id=user_id,
                session_id=final_state.session_id,
            )
            records.append(_record(
                memory_id=memory_id,
                user_id=user_id,
                session_id=final_state.session_id,
                kind=MemoryKind.PROFILE_FACT,
                content=content,
                data={"fact": fact.model_dump()},
                source={"type": "candidate_profile.fact", "id": fact.id, "refs": fact.source_refs},
            ))
        return records

    def _resume_artifact_memories(self, final_state: CopilotState, user_id: str | None) -> list[MemoryRecord]:
        resume = final_state.resume_content_json
        if not resume:
            return []

        records: list[MemoryRecord] = []
        sections: list[tuple[str, Iterable[SectionItem]]] = [
            ("skills", resume.skills),
            ("internships", resume.internships),
            ("projects", resume.projects),
            ("awards", resume.awards),
            ("papers", resume.papers),
        ]
        for section, items in sections:
            for item in items:
                records.append(self._section_item_record(final_state, user_id, section, item))
        if resume.summary:
            source_id = f"resume:summary:v{resume.meta.version}"
            records.append(_record(
                memory_id=build_memory_id(
                    kind=MemoryKind.ARTIFACT,
                    source_id=source_id,
                    user_id=user_id,
                    session_id=final_state.session_id,
                ),
                user_id=user_id,
                session_id=final_state.session_id,
                kind=MemoryKind.ARTIFACT,
                content=compact_text(f"resume summary: {resume.summary}"),
                data={"summary": resume.summary, "version": resume.meta.version},
                source={"type": "resume_content.summary", "id": source_id},
            ))
        return records

    def _section_item_record(
        self,
        final_state: CopilotState,
        user_id: str | None,
        section: str,
        item: SectionItem,
    ) -> MemoryRecord:
        source_id = f"resume:{section}:{item.id}"
        content = compact_text(f"{section}: {item.title}\n{item.content}")
        return _record(
            memory_id=build_memory_id(
                kind=MemoryKind.ARTIFACT,
                source_id=source_id,
                user_id=user_id,
                session_id=final_state.session_id,
            ),
            user_id=user_id,
            session_id=final_state.session_id,
            kind=MemoryKind.ARTIFACT,
            content=content,
            data={"section": section, "item": item.model_dump()},
            source={"type": "resume_content.section_item", "id": source_id, "section": section},
        )

    def _material_artifact_memories(
        self,
        old_state: CopilotState | None,
        final_state: CopilotState,
        user_id: str | None,
    ) -> list[MemoryRecord]:
        profile = final_state.candidate_profile
        if not profile:
            return []

        old_material_ids = set()
        if old_state and old_state.candidate_profile:
            old_material_ids = {item.material_id for item in old_state.candidate_profile.materials}

        records: list[MemoryRecord] = []
        for material in profile.materials:
            if material.material_id in old_material_ids:
                continue
            records.append(self._material_record(final_state, user_id, material))
        return records

    def _material_record(
        self,
        final_state: CopilotState,
        user_id: str | None,
        material: Material,
    ) -> MemoryRecord:
        content = compact_text(f"source material ({material.type}): {material.content}")
        return _record(
            memory_id=build_memory_id(
                kind=MemoryKind.ARTIFACT,
                source_id=f"material:{material.material_id}",
                user_id=user_id,
                session_id=final_state.session_id,
            ),
            user_id=user_id,
            session_id=final_state.session_id,
            kind=MemoryKind.ARTIFACT,
            content=content,
            data={"material": material.model_dump()},
            source={"type": "candidate_profile.material", "id": material.material_id},
        )

    def _interview_artifact_memories(self, final_state: CopilotState, user_id: str | None) -> list[MemoryRecord]:
        records: list[MemoryRecord] = []
        for qa in final_state.interview_qa:
            records.append(self._interview_record(final_state, user_id, qa))
        return records

    def _interview_record(
        self,
        final_state: CopilotState,
        user_id: str | None,
        qa: InterviewQA,
    ) -> MemoryRecord:
        source_id = f"interview:{qa.id}"
        content = compact_text(f"interview {qa.category}: {qa.question}\nanswer: {qa.answer}")
        return _record(
            memory_id=build_memory_id(
                kind=MemoryKind.ARTIFACT,
                source_id=source_id,
                user_id=user_id,
                session_id=final_state.session_id,
            ),
            user_id=user_id,
            session_id=final_state.session_id,
            kind=MemoryKind.ARTIFACT,
            content=content,
            data={"interview_qa": qa.model_dump()},
            source={"type": "interview_qa", "id": source_id, "refs": qa.source_refs},
        )

    def _explicit_preference_memory(
        self,
        final_state: CopilotState,
        user_message: str,
        user_id: str | None,
    ) -> MemoryRecord | None:
        if not _looks_like_preference(user_message):
            return None
        content = compact_text(user_message, max_chars=1200)
        source_id = f"preference:{content_hash(content)[:16]}"
        return _record(
            memory_id=build_memory_id(
                kind=MemoryKind.PREFERENCE,
                source_id=source_id,
                user_id=user_id,
                session_id=final_state.session_id,
            ),
            user_id=user_id,
            session_id=final_state.session_id,
            kind=MemoryKind.PREFERENCE,
            content=content,
            data={
                "raw_user_message": user_message,
                "render_config": final_state.render_config.model_dump(),
            },
            source={"type": "user_explicit_preference", "id": source_id},
            confidence=0.8,
        )


def _record(
    *,
    memory_id: str,
    user_id: str | None,
    session_id: str | None,
    kind: MemoryKind,
    content: str,
    data: dict,
    source: dict,
    confidence: float = 1.0,
) -> MemoryRecord:
    now = utc_now()
    return MemoryRecord(
        memory_id=memory_id,
        user_id=user_id,
        session_id=session_id,
        scope=MemoryScope.USER if user_id else MemoryScope.SESSION,
        kind=kind,
        content=content,
        data=data,
        source=source,
        confidence=confidence,
        status=MemoryStatus.ACTIVE,
        content_hash=content_hash(content),
        created_at=now,
        updated_at=now,
    )


def _looks_like_preference(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    markers = [
        "记住",
        "以后",
        "默认",
        "偏好",
        "喜欢",
        "不喜欢",
        "倾向",
        "保持",
        "下次",
        "每次",
    ]
    return any(marker in text for marker in markers)


def _dedupe(records: list[MemoryRecord]) -> list[MemoryRecord]:
    seen: set[str] = set()
    unique: list[MemoryRecord] = []
    for record in records:
        if record.memory_id in seen:
            continue
        seen.add(record.memory_id)
        unique.append(record)
    return unique
