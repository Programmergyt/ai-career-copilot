"""工作流状态定义 — LangGraph 状态类型"""

from typing import Optional
from typing_extensions import TypedDict


class WorkflowState(TypedDict):
    """LangGraph 工作流状态，贯穿整个 Pipeline。"""

    # ---- 输入 ----
    jd_text: str                          # JD 原文
    personal_docs: list[str]              # 个人材料文件路径列表
    template_path: str                    # 简历模板路径

    # ---- 中间状态 ----
    parsed_docs: Optional[list[dict]]     # 解析后的文档列表 [{"text": str, "source_file": str, "doc_type": str}]
    profile: Optional[dict]               # 提取的个人基本信息（姓名、电话、邮箱、学历、教育背景等）
    jd_analysis: Optional[dict]           # JD 分析结果（结构化 JSON）
    matched_sections: Optional[dict]      # 按类型分别 RAG 检索的结果 {"project": [...], "internship": [...], "skill": [...], "paper": [...]}
    resume_data: Optional[dict]           # 简历结构化数据（JSON dict，包含 name/skills/projects 等字段）
    resume_draft: Optional[str]           # 简历草稿（渲染后的 Markdown）
    resume_final: Optional[str]           # 最终简历内容

    # ---- 输出 ----
    resume_file: Optional[str]            # 输出文件路径
    interview_qa: Optional[str]           # 面试 Q&A（第一期不实现）
    analysis_log: list[str]               # 过程日志

    # ---- 控制 ----
    current_step: str                     # 当前步骤名称
    error: Optional[str]                  # 错误信息
