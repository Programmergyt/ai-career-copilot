"""Export content generation service."""

from __future__ import annotations

import json
from dataclasses import dataclass

from workflow.state import CopilotState, Gap, InterviewQA, Job, Question


class ExportError(Exception):
    """Raised when an export target or format cannot be generated."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class ExportResult:
    content: str
    media_type: str
    filename: str


def export_state(state: CopilotState, target: str, export_format: str) -> ExportResult:
    normalized_target = (target or "resume").strip().lower()
    normalized_format = (export_format or "html").strip().lower()

    if normalized_target == "resume":
        return _export_resume(state, normalized_format, export_format)
    if normalized_target == "job":
        return _export_job(state, normalized_format, export_format)
    if normalized_target == "gaps":
        return _export_gaps(state, normalized_format, export_format)
    if normalized_target == "interview":
        return _export_interview(state, normalized_format, export_format)

    raise ExportError(f"不支持的导出对象: {target}")


def _export_resume(state: CopilotState, normalized_format: str, requested_format: str) -> ExportResult:
    if normalized_format == "html":
        if not state.resume_html.html:
            raise ExportError("简历 HTML 尚未生成", status_code=404)
        return ExportResult(state.resume_html.html, "text/html", "resume.html")
    if normalized_format == "json":
        return ExportResult(_export_resume_json(state), "application/json", "resume.json")
    if normalized_format in {"markdown", "md"}:
        return ExportResult(_export_resume_markdown(state), "text/markdown", "resume.md")
    raise ExportError(f"简历导出不支持格式: {requested_format}")


def _export_job(state: CopilotState, normalized_format: str, requested_format: str) -> ExportResult:
    if state.job is None:
        raise ExportError("岗位解析尚未生成", status_code=404)
    if normalized_format == "json":
        return ExportResult(_export_job_json(state.job), "application/json", "job-analysis.json")
    if normalized_format == "txt":
        return ExportResult(_export_job_text(state.job), "text/plain", "job-analysis.txt")
    if normalized_format in {"markdown", "md"}:
        return ExportResult(_export_job_markdown(state.job), "text/markdown", "job-analysis.md")
    raise ExportError(f"岗位解析导出不支持格式: {requested_format}")


def _export_gaps(state: CopilotState, normalized_format: str, requested_format: str) -> ExportResult:
    if not state.gaps and not state.questions_to_ask:
        raise ExportError("缺失信息尚未生成", status_code=404)
    if normalized_format == "json":
        return ExportResult(_export_gaps_json(state.gaps, state.questions_to_ask), "application/json", "gaps.json")
    if normalized_format == "txt":
        return ExportResult(_export_gaps_text(state.gaps, state.questions_to_ask), "text/plain", "gaps.txt")
    if normalized_format in {"markdown", "md"}:
        return ExportResult(_export_gaps_markdown(state.gaps, state.questions_to_ask), "text/markdown", "gaps.md")
    raise ExportError(f"缺失信息导出不支持格式: {requested_format}")


def _export_interview(state: CopilotState, normalized_format: str, requested_format: str) -> ExportResult:
    if not state.interview_qa:
        raise ExportError("面试问答尚未生成", status_code=404)
    if normalized_format == "json":
        return ExportResult(_export_interview_json(state.interview_qa), "application/json", "interview-qa.json")
    if normalized_format == "txt":
        return ExportResult(_export_interview_text(state.interview_qa), "text/plain", "interview-qa.txt")
    if normalized_format in {"markdown", "md"}:
        return ExportResult(_export_interview_markdown(state.interview_qa), "text/markdown", "interview-qa.md")
    raise ExportError(f"面试问答导出不支持格式: {requested_format}")


def _export_job_json(job: Job) -> str:
    return json.dumps(job.model_dump(), ensure_ascii=False, indent=2)


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- -"]


def _export_job_text(job: Job) -> str:
    sections = [
        "岗位解析",
        f"岗位名称: {job.title or '-'}",
        f"行业: {job.industry or '-'}",
        f"学历要求: {job.education_requirement or '-'}",
        f"经验要求: {job.experience_requirement or '-'}",
        "",
        "技术栈:",
        *_bullet_lines(job.tech_stack),
        "",
        "硬技能:",
        *_bullet_lines(job.hard_skills),
        "",
        "软技能:",
        *_bullet_lines(job.soft_skills),
        "",
        "职责:",
        *_bullet_lines(job.responsibilities),
        "",
        "关键词:",
        *_bullet_lines(job.keywords),
        "",
        "隐含偏好:",
        *_bullet_lines(job.implicit_preferences),
        "",
        "加分项:",
        *_bullet_lines(job.bonus_items),
    ]
    return "\n".join(sections)


def _export_job_markdown(job: Job) -> str:
    lines = [
        "# 岗位解析",
        "",
        f"- 岗位名称: {job.title or '-'}",
        f"- 行业: {job.industry or '-'}",
        f"- 学历要求: {job.education_requirement or '-'}",
        f"- 经验要求: {job.experience_requirement or '-'}",
        "",
        "## 技术栈",
        *_bullet_lines(job.tech_stack),
        "",
        "## 硬技能",
        *_bullet_lines(job.hard_skills),
        "",
        "## 软技能",
        *_bullet_lines(job.soft_skills),
        "",
        "## 职责",
        *_bullet_lines(job.responsibilities),
        "",
        "## 关键词",
        *_bullet_lines(job.keywords),
        "",
        "## 隐含偏好",
        *_bullet_lines(job.implicit_preferences),
        "",
        "## 加分项",
        *_bullet_lines(job.bonus_items),
    ]
    return "\n".join(lines)


def _export_gaps_json(gaps: list[Gap], questions: list[Question]) -> str:
    payload = {
        "gaps": [item.model_dump() for item in gaps],
        "questions_to_ask": [item.model_dump() for item in questions],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _export_gaps_text(gaps: list[Gap], questions: list[Question]) -> str:
    lines = ["缺失信息与能力缺口", "", f"待补充信息: {len(questions)} 项"]
    if questions:
        for index, item in enumerate(questions, start=1):
            lines.extend([
                f"{index}. {item.question}",
                f"   优先级: {item.priority or '-'}",
                f"   目标字段: {item.target_field or '-'}",
                f"   原因: {item.reason or '-'}",
                f"   状态: {item.status or '-'}",
            ])
    else:
        lines.append("- 暂无待补充信息")

    lines.extend(["", f"能力缺口: {len(gaps)} 项"])
    if gaps:
        for index, item in enumerate(gaps, start=1):
            section_ids = ", ".join(item.related_section_ids) if item.related_section_ids else "-"
            lines.extend([
                f"{index}. {item.description or item.type}",
                f"   类型: {item.type or '-'}",
                f"   严重程度: {item.severity or '-'}",
                f"   关联 section: {section_ids}",
                f"   已解决: {'是' if item.resolved else '否'}",
            ])
    else:
        lines.append("- 暂无能力缺口")

    return "\n".join(lines)


def _export_gaps_markdown(gaps: list[Gap], questions: list[Question]) -> str:
    lines = ["# 缺失信息与能力缺口", "", "## 待补充信息"]
    if questions:
        for item in questions:
            lines.extend([
                f"- 问题: {item.question}",
                f"  原因: {item.reason or '-'}",
                f"  目标字段: {item.target_field or '-'}",
                f"  优先级: {item.priority or '-'}",
                f"  状态: {item.status or '-'}",
            ])
    else:
        lines.append("- 暂无待补充信息")

    lines.extend(["", "## 能力缺口"])
    if gaps:
        for item in gaps:
            lines.extend([
                f"- 描述: {item.description or item.type}",
                f"  类型: {item.type or '-'}",
                f"  严重程度: {item.severity or '-'}",
                f"  关联 section: {', '.join(item.related_section_ids) if item.related_section_ids else '-'}",
                f"  已解决: {'是' if item.resolved else '否'}",
            ])
    else:
        lines.append("- 暂无能力缺口")

    return "\n".join(lines)


def _export_interview_json(interview_qa: list[InterviewQA]) -> str:
    payload = {"interview_qa": [item.model_dump() for item in interview_qa]}
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _export_interview_text(interview_qa: list[InterviewQA]) -> str:
    lines = ["面试问答", "", f"共 {len(interview_qa)} 道题"]
    if not interview_qa:
        lines.append("- 暂无面试问答")
        return "\n".join(lines)

    for index, item in enumerate(interview_qa, start=1):
        refs = ", ".join(item.source_refs) if item.source_refs else "-"
        lines.extend([
            "",
            f"Q{index}. {item.question}",
            f"类别: {item.category or '-'}",
            "参考答案:",
            item.answer or "-",
            f"来源引用: {refs}",
        ])
    return "\n".join(lines)


def _export_interview_markdown(interview_qa: list[InterviewQA]) -> str:
    lines = ["# 面试问答", "", f"共 {len(interview_qa)} 道题"]
    if not interview_qa:
        lines.extend(["", "- 暂无面试问答"])
        return "\n".join(lines)

    for index, item in enumerate(interview_qa, start=1):
        lines.extend([
            "",
            f"## Q{index}. {item.question}",
            f"- 类别: {item.category or '-'}",
            f"- 来源引用: {', '.join(item.source_refs) if item.source_refs else '-'}",
            "",
            "### 参考答案",
            item.answer or "-",
        ])
    return "\n".join(lines)


def _export_resume_json(state: CopilotState) -> str:
    if state.resume_content_json is None:
        raise ExportError("简历内容尚未生成", status_code=404)
    return json.dumps(state.resume_content_json.model_dump(), ensure_ascii=False, indent=2)


def _export_resume_markdown(state: CopilotState) -> str:
    if state.resume_content_json is None:
        raise ExportError("简历内容尚未生成", status_code=404)

    content = state.resume_content_json
    profile = content.profile
    lines = [
        "# 简历内容",
        "",
        "## 基本信息",
        f"- 姓名: {profile.name or '-'}",
        f"- 邮箱: {profile.email or '-'}",
        f"- 电话: {profile.phone or '-'}",
        f"- 城市: {profile.city or '-'}",
        f"- GitHub: {profile.github or '-'}",
        "",
        "## 个人总结",
        content.summary or "-",
    ]

    sections = [
        ("技能", content.skills),
        ("项目", content.projects),
        ("实习", content.internships),
        ("奖项", content.awards),
        ("论文", content.papers),
    ]
    for title, items in sections:
        lines.extend(["", f"## {title}"])
        if not items:
            lines.append("- -")
            continue
        for item in items:
            lines.extend([f"- {item.title}", f"  {item.content}"])
    return "\n".join(lines)
