"""简历自检 Prompt 模板"""

SELF_CHECK_SYSTEM = """你是一位简历质检专家。你的任务是检查简历是否充分覆盖了 JD 的核心要求。"""

SELF_CHECK_USER = """## JD 分析结果
{jd_analysis}

## 当前简历内容
{resume_content}

请检查简历质量，返回 JSON（不要包含 ```json 标记）：
{{
    "coverage_score": 0.0 到 1.0 的覆盖度评分,
    "covered_requirements": ["已覆盖的 JD 要求1", ...],
    "missing_requirements": ["未覆盖的 JD 要求1", ...],
    "improvement_suggestions": ["改进建议1", ...],
    "pass": true 或 false（覆盖度 >= 0.7 为 true）
}}"""
