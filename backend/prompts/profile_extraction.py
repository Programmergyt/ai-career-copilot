"""Profile 提取 Prompt。"""

PROFILE_EXTRACTION_PROMPT = """你是一个候选人画像构建专家。请从以下用户提供的材料中提取结构化信息。

用户材料：
{material_text}

已有画像（如有）：
{existing_profile}

机器协议：
- 返回且仅返回一个合法 JSON 对象
- 不要输出 Markdown、代码块、注释或额外说明
- 所有 key 必须使用双引号
- 所有字符串中的双引号必须转义

返回格式如下，并将信息合并到已有画像中（增量更新，不覆盖已有数据）：
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
5. 即使信息不足，也必须返回合法 JSON 对象
6. 保留已有画像中的信息，只添加或更新
"""
