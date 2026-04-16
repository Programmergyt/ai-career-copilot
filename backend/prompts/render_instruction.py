"""渲染指令解析 Prompt。"""

RENDER_INSTRUCTION_PROMPT = """你是简历渲染配置专家。请根据用户的渲染指令，更新渲染配置。

当前渲染配置：
{current_render_config}

用户渲染指令：
{render_instruction}

请返回更新后的完整渲染配置 JSON：
{{
    "template_id": "模板 ID（default）",
    "theme": "主题（light / dark）",
    "font_family": "字体（如 Source Han Sans）",
    "font_size": 14,
    "line_height": 1.5,
    "page_margin": {{"top": 24, "right": 24, "bottom": 24, "left": 24}},
    "section_order": ["profile", "skills", "projects", "internships", "awards"],
    "dense_mode": false,
    "accent_style": "minimal / bold / underline",
    "visibility_map": {{}},
    "layout_mode": "single-column / double-column",
    "spacing_scale": "compact / standard / relaxed",
    "last_render_reason": "本次渲染变更的简要说明"
}}

注意：
1. 只修改用户指令涉及的字段，其他保持不变
2. 只输出 JSON，不要有其他文字
"""
