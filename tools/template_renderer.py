"""HTML 简历渲染引擎 — 将 ResumeContent + RenderConfig → HTML 字符串。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from log import get_logger

if TYPE_CHECKING:
    from workflow.state import ResumeContent, RenderConfig

logger = get_logger("app")

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def render_resume_html(content: "ResumeContent", config: "RenderConfig") -> str:
    """根据简历内容和渲染配置生成 HTML 字符串。"""
    template_path = _TEMPLATE_DIR / f"{config.template_id}.html"
    if not template_path.exists():
        template_path = _TEMPLATE_DIR / "default.html"

    template = template_path.read_text(encoding="utf-8")

    # 构建模板变量
    variables = _build_template_variables(content, config)

    # 简单变量替换
    html = template
    for key, value in variables.items():
        html = html.replace(f"{{{{{key}}}}}", str(value))

    logger.info("Resume HTML rendered with template=%s", config.template_id)
    return html


def _build_template_variables(content: "ResumeContent", config: "RenderConfig") -> dict:
    """构建模板替换变量。"""
    # CSS 变量
    margin = config.page_margin
    spacing = {"compact": 0.8, "standard": 1.0, "relaxed": 1.2}.get(config.spacing_scale, 1.0)

    css_vars = f"""
        --font-family: '{config.font_family}', sans-serif;
        --font-size: {config.font_size}px;
        --line-height: {config.line_height};
        --margin-top: {margin.top}px;
        --margin-right: {margin.right}px;
        --margin-bottom: {margin.bottom}px;
        --margin-left: {margin.left}px;
        --spacing-scale: {spacing};
    """

    # Profile section
    profile = content.profile
    edu_html = ""
    for edu in profile.education:
        edu_html += f'<div class="edu-item"><span class="edu-school">{edu.school}</span>'
        edu_html += f'<span class="edu-detail">{edu.major} · {edu.degree} · {edu.start_date} - {edu.end_date}</span></div>'

    # Section HTML generators
    def _render_items(items, section_class: str) -> str:
        parts = []
        for item in items:
            # 处理 content 中的换行
            formatted_content = item.content.replace("\n", "<br>")
            parts.append(
                f'<div class="item {section_class}-item">'
                f'<h3 class="item-title">{item.title}</h3>'
                f'<div class="item-content">{formatted_content}</div>'
                f'</div>'
            )
        return "\n".join(parts)

    # 按 section_order 排列
    sections_html_map = {
        "profile": f"""
            <section class="section section-profile">
                <h2>基本信息</h2>
                <div class="profile-info">
                    <span class="name">{profile.name}</span>
                    <span class="contact">{profile.email} | {profile.phone} | {profile.city}</span>
                    {'<span class="github">' + profile.github + '</span>' if profile.github else ''}
                </div>
                <div class="education">{edu_html}</div>
            </section>
        """,
        "summary": f"""
            <section class="section section-summary">
                <h2>个人总结</h2>
                <p>{content.summary}</p>
            </section>
        """ if content.summary else "",
        "skills": f"""
            <section class="section section-skills">
                <h2>专业技能</h2>
                {_render_items(content.skills, 'skill')}
            </section>
        """ if content.skills else "",
        "internships": f"""
            <section class="section section-internships">
                <h2>实习经历</h2>
                {_render_items(content.internships, 'internship')}
            </section>
        """ if content.internships else "",
        "projects": f"""
            <section class="section section-projects">
                <h2>项目经历</h2>
                {_render_items(content.projects, 'project')}
            </section>
        """ if content.projects else "",
        "awards": f"""
            <section class="section section-awards">
                <h2>获奖经历</h2>
                {_render_items(content.awards, 'award')}
            </section>
        """ if content.awards else "",
        "papers": f"""
            <section class="section section-papers">
                <h2>论文</h2>
                {_render_items(content.papers, 'paper')}
            </section>
        """ if content.papers else "",
    }

    # 根据 section_order 和 visibility_map 排列
    ordered_sections = []
    for section_name in config.section_order:
        if config.visibility_map.get(section_name, True) is False:
            continue
        html = sections_html_map.get(section_name, "")
        if html:
            ordered_sections.append(html)

    # 添加 section_order 中没有列出但存在内容的 section
    for section_name, html in sections_html_map.items():
        if section_name not in config.section_order and html:
            if config.visibility_map.get(section_name, True) is not False:
                ordered_sections.append(html)

    layout_class = "double-column" if config.layout_mode == "double-column" else "single-column"
    dense_class = "dense" if config.dense_mode else ""
    theme_class = config.theme

    return {
        "CSS_VARIABLES": css_vars,
        "LAYOUT_CLASS": layout_class,
        "DENSE_CLASS": dense_class,
        "THEME_CLASS": theme_class,
        "SECTIONS_HTML": "\n".join(ordered_sections),
        "NAME": profile.name,
        "TARGET_ROLE": content.meta.target_role,
    }
