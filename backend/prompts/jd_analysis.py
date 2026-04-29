"""JD 解析 Prompt。"""

JD_ANALYSIS_PROMPT = """你是一个专业的岗位需求分析专家。请仔细分析以下岗位描述（JD），提取结构化信息。

岗位描述原文：
{jd_text}

机器协议：
- 返回且仅返回一个合法 JSON 对象
- 不要输出 Markdown、代码块、注释或额外说明
- 所有 key 必须使用双引号
- 所有字符串中的双引号必须转义
- section_rationales 用于给用户展示简要决策依据，不要输出内部逐步推理；每条 1 句话即可

返回格式如下：
{{
    "industry": "行业（如：互联网、金融、制造业等）",
    "title": "岗位名称",
    "tech_stack": ["技术栈1", "技术栈2"],
    "keywords": ["核心关键词1", "核心关键词2"],
    "hard_skills": ["硬技能1", "硬技能2"],
    "soft_skills": ["软技能1", "软技能2"],
    "responsibilities": ["职责1", "职责2"],
    "education_requirement": "学历要求",
    "experience_requirement": "经验要求",
    "implicit_preferences": ["隐含偏好1"],
    "bonus_items": ["加分项1"],
    "section_rationales": [
        {{
            "section": "岗位分析",
            "decision": "提取岗位名称、技术栈、职责和加分项",
            "reason": "说明这些信息会如何影响后续的简历匹配、内容排序或面试准备",
            "evidence": ["JD 中的关键词或短句"]
        }}
    ]
}}

注意：
1. 技术栈要具体到技术名称和版本（如有提及）
2. 隐含偏好是指 JD 中没有直接说明但暗示的要求
3. 如果某个字段信息不明确，使用空字符串或空列表
4. 即使信息不足，也必须返回合法 JSON 对象
"""
