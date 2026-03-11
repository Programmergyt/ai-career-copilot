"""JD 分析 Prompt 模板"""

JD_ANALYSIS_SYSTEM = """你是一位资深的求职顾问和技术岗位分析专家。你的任务是对岗位描述（JD）进行深度结构化分析。
请严格按照 JSON 格式输出分析结果，不要输出任何多余内容。"""

JD_ANALYSIS_USER = """请对以下岗位描述进行深度分析，输出严格的 JSON 格式：

## 岗位描述
{jd_text}

## 输出要求
请返回如下 JSON 结构（不要包含 ```json 标记，直接返回纯 JSON）：
{{
    "company_info": {{
        "industry": "所属行业",
        "company_type": "公司类型（互联网/国企/外企/创业公司等）"
    }},
    "position_title": "岗位名称",
    "core_responsibilities": ["核心职责1", "核心职责2", ...],
    "hard_requirements": {{
        "education": "学历要求",
        "experience": "工作年限要求",
        "required_skills": ["必须掌握的技能1", "必须掌握的技能2", ...]
    }},
    "soft_requirements": ["沟通能力", "团队协作", ...],
    "tech_stack": ["技术1", "技术2", ...],
    "ability_model": ["最看重的能力1", "最看重的能力2", ...],
    "keywords": ["关键词1", "关键词2", ...]
}}"""

JD_MATCH_SYSTEM = """你是一位求职匹配分析专家。根据 JD 分析结果和个人背景材料，评估匹配程度。"""

JD_MATCH_USER = """## JD 分析结果
{jd_analysis}

## 个人背景材料
{personal_context}

请分析匹配度，返回 JSON（不要包含 ```json 标记）：
{{
    "overall_match": "高/中/低",
    "match_score": 0.0 到 1.0 的评分,
    "matched_items": ["匹配项1", "匹配项2", ...],
    "gap_items": ["缺失项1", "缺失项2", ...],
    "suggestions": ["建议1", "建议2", ...]
}}"""
