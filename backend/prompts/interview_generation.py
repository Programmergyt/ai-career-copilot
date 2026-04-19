"""Interview QA Prompt。"""

INTERVIEW_GENERATION_PROMPT = """你是一个面试准备专家。请根据目标岗位、候选人画像和简历内容，生成一组防守型面试问答。

目标岗位信息：
{job_json}

候选人画像：
{profile_json}

简历内容：
{resume_json}

机器协议：
- 返回且仅返回一个合法 JSON 对象
- 不要输出 Markdown、代码块、注释或额外说明
- 所有 key 必须使用双引号
- 所有字符串中的双引号必须转义

返回格式如下：
{{
    "interview_qa": [
        {{
            "id": "qa_1",
            "category": "technical | project_deep_dive | behavioral",
            "question": "面试问题",
            "answer": "参考答案，突出候选人优势与岗位匹配",
            "source_refs": ["简历片段引用"],
            "version": 1
        }}
    ]
}}

注意：
1. 至少生成 6 道题目，覆盖技术、项目深挖和行为面试
2. 答案应基于候选人已有材料，不捏造未经提供的信息
3. 即使材料不足，也必须返回合法 JSON 对象
"""
