"""Gap Analysis Prompt。"""

GAP_ANALYSIS_PROMPT = """你是一个能力缺口分析专家。请根据以下岗位要求和候选人画像，分析候选人相对于岗位的能力缺口，并给出需要补充的追问问题。

目标岗位信息：
{job_json}

候选人画像：
{profile_json}

请严格按照以下 JSON 格式输出：
{{
    "gaps": [
        {{
            "id": "gap_1",
            "type": "missing_skill | missing_experience | no_quantification | low_relevance",
            "severity": "high | medium | low",
            "description": "能力缺口描述",
            "related_section_ids": ["section_id"],
            "resolved": false,
            "resolution_source": "gap_analysis"
        }}
    ],
    "questions_to_ask": [
        {{
            "id": "q_1",
            "question": "你有 RAG 项目经验吗？",
            "reason": "补充候选人项目经验的关键细节",
            "target_field": "projects",
            "priority": "high",
            "status": "pending",
            "answer_ref": ""
        }}
    ]
}}

注意：
1. 如果没有候选人画像或岗位信息，输出空数组
2. 不要输出额外说明文字，仅返回 JSON
"""
