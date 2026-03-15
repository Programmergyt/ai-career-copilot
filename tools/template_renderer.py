"""模板渲染工具 — 将结构化简历数据（JSON）填充到 Markdown 模板"""

import re
from pathlib import Path
from string import Template


def render_markdown(template_path: str, context: dict) -> str:
    """读取 Markdown 模板并用 context 字典填充。

    模板使用 Python string.Template 语法：$variable 或 ${variable}。
    """
    tpl_text = Path(template_path).read_text(encoding="utf-8")
    template = Template(tpl_text)
    return template.safe_substitute(context)


# ------------------------------------------------------------------
# 简历专用渲染
# ------------------------------------------------------------------

# 可选板块：(JSON 字段名, 模板中的板块标题)
_OPTIONAL_SECTIONS = [
    ("skills", "专业技能"),
    ("projects", "项目经历"),
    ("internship", "实习经历"),
    ("papers", "论文与学术成果"),
    ("awards", "获奖与证书"),
]


def render_resume(template_path: str, resume_data: dict) -> str:
    """将结构化简历数据渲染为 Markdown。

    会自动跳过无内容的可选板块（专业技能、项目经历、实习经历、论文、获奖）。

    Args:
        template_path: Markdown 模板路径
        resume_data: 简历 JSON 数据 (name, email, phone, github, education, skills, projects, ...)

    Returns:
        渲染后的 Markdown 文本
    """
    context = _build_resume_context(resume_data)
    rendered = render_markdown(template_path, context)
    # 清理多余空行
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.strip() + "\n"


def _build_resume_context(data: dict) -> dict:
    """从简历 JSON 数据构建模板渲染上下文。"""
    # 联系方式行
    parts = []
    if data.get("email"):
        parts.append(data["email"])
    if data.get("phone"):
        parts.append(data["phone"])
    if data.get("github"):
        parts.append(data["github"])
    contact = " | ".join(parts) if parts else "TODO: 联系方式"

    context = {
        "name": data.get("name") or "TODO: 姓名",
        "contact": contact,
        "education": data.get("education") or "TODO: 教育背景",
    }

    # 构建可选板块 — 有内容时输出 "---\n\n## 标题\n\n内容"，无内容时为空串
    blocks = []
    for key, header in _OPTIONAL_SECTIONS:
        content = (data.get(key) or "").strip()
        if content:
            blocks.append(f"\n---\n\n## {header}\n\n{content}")

    context["optional_sections"] = "\n".join(blocks)
    return context


def save_output(content: str, output_path: str) -> str:
    """将内容保存到文件，返回绝对路径。"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path.resolve())
