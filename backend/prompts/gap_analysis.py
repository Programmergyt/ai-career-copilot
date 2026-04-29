"""Gap Analysis Prompt。"""

GAP_ANALYSIS_PROMPT = """你是一个能力缺口分析专家。请根据以下岗位要求和候选人画像，分析候选人相对于岗位的能力缺口，并给出需要补充的追问问题。

目标岗位信息：
{job_json}

候选人画像：
{profile_json}

机器协议：
- 返回且仅返回一个合法 JSON 对象
- 不要输出 Markdown、代码块、注释或额外说明
- 所有 key 必须使用双引号
- 所有字符串中的双引号必须转义
- section_rationales 用于给用户展示简要决策依据，不要输出内部逐步推理；每条 1 句话即可

返回格式如下：
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
    ],
    "section_rationales": [
        {{
            "section": "匹配差距",
            "decision": "对照岗位要求和候选人事实识别能力缺口与追问问题",
            "reason": "说明为什么这些缺口或问题会影响岗位匹配度",
            "evidence": ["岗位要求或候选人画像中的简短依据"]
        }}
    ]
}}

注意：
1. 如果没有候选人画像或岗位信息，输出空数组
2. 即使没有结果，也必须返回合法 JSON 对象
"""
