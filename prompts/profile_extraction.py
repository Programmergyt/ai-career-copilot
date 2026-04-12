"""Profile 提取 Prompt。"""

PROFILE_EXTRACTION_PROMPT = """你是一个候选人画像构建专家。请从以下用户提供的材料中提取结构化信息。

用户材料：
{material_text}

已有画像（如有）：
{existing_profile}

请严格按照以下 JSON 格式输出，将信息合并到已有画像中（增量更新，不覆盖已有数据）：
{{
    "profile_basic": {{
        "name": "姓名",
        "email": "邮箱",
        "phone": "电话",
        "city": "城市",
        "school": "学校"
    }},
    "facts": [
        {{
            "id": "fact_<type>_<序号>",
            "type": "skill | project | internship | award | paper",
            "content": "结构化描述内容（JSON 格式的字符串，包含关键细节）",
            "source_refs": ["material_<id>"],
            "updated_at": ""
        }}
    ]
}}

注意：
1. type 只能是: skill, project, internship, award, paper 之一
2. content 字段应包含足够的细节，便于后续简历生成
3. 对于项目和实习，content 应包含：名称、时间、角色、技术栈、职责、成果
4. 对于技能，content 应包含：技能名称、熟练程度、应用场景
5. 只输出 JSON，不要有其他文字
6. 保留已有画像中的信息，只添加或更新
"""
