"""LangGraph 工作流编排 — 串联 JD 分析 → 简历生成 MVP Pipeline"""

import json
from langgraph.graph import StateGraph, END

from workflow.state import WorkflowState
from tools.file_parser import parse_file, parse_directory
from rag.indexer import build_index
from rag.retriever import retrieve
from agents.jd_analyzer import analyze_jd
from agents.resume_writer import generate_resume, self_check_resume
from agents.doc_classifier import classify_documents, extract_profile
from tools.template_renderer import save_output, render_resume


# ============================================================
# 节点函数：每个节点接收并返回 WorkflowState
# ============================================================

def node_parse_documents(state: WorkflowState) -> dict:
    """解析个人材料文档（仅解析，不入库）。"""
    logs = list(state.get("analysis_log") or [])
    logs.append("[1/8] 开始解析个人材料文档...")

    parsed_docs = []
    for fpath in state["personal_docs"]:
        from pathlib import Path
        p = Path(fpath)
        if p.is_dir():
            dir_results = parse_directory(fpath)
            for sub_path, text in dir_results.items():
                if text.startswith("[解析失败]"):
                    logs.append(f"  ✗ 解析失败: {sub_path} — {text}")
                else:
                    parsed_docs.append({
                        "text": text,
                        "source_file": sub_path,
                        "doc_type": "personal",  # 初始类型，后续由 LLM 分类
                    })
                    logs.append(f"  ✓ 解析成功: {sub_path}")
        else:
            try:
                text = parse_file(fpath)
                parsed_docs.append({
                    "text": text,
                    "source_file": fpath,
                    "doc_type": "personal",
                })
                logs.append(f"  ✓ 解析成功: {fpath}")
            except Exception as e:
                logs.append(f"  ✗ 解析失败: {fpath} — {e}")

    logs.append(f"  → 共解析 {len(parsed_docs)} 份文档")

    return {
        "parsed_docs": parsed_docs,
        "current_step": "parse_documents",
        "analysis_log": logs,
    }


def node_classify_documents(state: WorkflowState) -> dict:
    """使用 LLM 对文档进行分类（profile/project/internship/skill/paper）。"""
    logs = list(state.get("analysis_log") or [])
    logs.append("[2/8] 文档分类中...")

    parsed_docs = list(state.get("parsed_docs") or [])
    if not parsed_docs:
        logs.append("  → 无文档可分类")
        return {"parsed_docs": parsed_docs, "current_step": "classify_documents", "analysis_log": logs}

    try:
        parsed_docs = classify_documents(parsed_docs)
        # 统计各类型数量
        type_counts = {}
        for doc in parsed_docs:
            t = doc["doc_type"]
            type_counts[t] = type_counts.get(t, 0) + 1
        for t, cnt in type_counts.items():
            logs.append(f"  → {t}: {cnt} 份")
        logs.append("  ✓ 文档分类完成")
    except Exception as e:
        logs.append(f"  ✗ 文档分类失败: {e}")

    return {
        "parsed_docs": parsed_docs,
        "current_step": "classify_documents",
        "analysis_log": logs,
    }


def node_extract_profile(state: WorkflowState) -> dict:
    """从 profile 类型文档中提取个人基本信息。"""
    logs = list(state.get("analysis_log") or [])
    logs.append("[3/8] 提取个人基本信息...")

    parsed_docs = state.get("parsed_docs") or []
    profile = None

    try:
        profile = extract_profile(parsed_docs)
        if profile and not profile.get("parse_error"):
            logs.append(f"  ✓ 提取成功 — 姓名: {profile.get('name', '未知')}")
        elif profile:
            logs.append("  ⚠ 信息提取结果解析异常，使用原始文本")
        else:
            logs.append("  → 未找到 profile 类型文档，跳过提取")
    except Exception as e:
        logs.append(f"  ✗ 提取失败: {e}")

    return {
        "profile": profile,
        "current_step": "extract_profile",
        "analysis_log": logs,
    }


# 需要参与 RAG 的文档类型及其对应的向量数据库 collection 名称
RAG_DOC_TYPES = ["项目经历", "实习经历", "专业技能", "论文成果"]

# 中文业务文档类型 -> 英文安全 collection 名称
DOC_TYPE_TO_COLLECTION = {
    "个人信息": "profile",
    "项目经历": "projects",
    "实习经历": "internships",
    "专业技能": "skills",
}


def _collection_name(doc_type: str) -> str:
    """根据文档类型生成对应的 collection 名称。"""
    name = DOC_TYPE_TO_COLLECTION.get(doc_type, "others")
    return f"personal_{name}"


def node_build_index(state: WorkflowState) -> dict:
    """按文档类型分别入库到独立的 RAG 向量数据库 collection。"""
    logs = list(state.get("analysis_log") or [])
    logs.append("[4/8] 构建 RAG 向量索引（按类型分库）...")

    parsed_docs = state.get("parsed_docs") or []

    total_indexed = 0
    for doc_type in RAG_DOC_TYPES:
        type_docs = [d for d in parsed_docs if d.get("doc_type") == doc_type]
        if not type_docs:
            continue

        texts = [d["text"] for d in type_docs]
        metas = [{"source_file": d["source_file"], "doc_type": d["doc_type"]} for d in type_docs]

        try:
            build_index(
                texts=texts,
                metadatas=metas,
                collection_name=_collection_name(doc_type),
            )
            logs.append(f"  → {doc_type}: 成功入库 {len(texts)} 份文档")
            total_indexed += len(texts)
        except Exception as e:
            logs.append(f"  → {doc_type}: 入库失败: {e}")

    if total_indexed == 0:
        logs.append("  → 无文档可入库")

    return {
        "current_step": "build_index",
        "analysis_log": logs,
    }


def node_analyze_jd(state: WorkflowState) -> dict:
    """JD 分析节点。"""
    logs = list(state.get("analysis_log") or [])
    logs.append("[5/8] 开始分析 JD...")

    try:
        jd_analysis = analyze_jd(state["jd_text"])
        logs.append("  ✓ JD 分析完成")
        logs.append(f"  → 提取技术栈: {jd_analysis.get('tech_stack', [])}")
        return {
            "jd_analysis": jd_analysis,
            "current_step": "analyze_jd",
            "analysis_log": logs,
        }
    except Exception as e:
        logs.append(f"  ✗ JD 分析失败: {e}")
        return {
            "error": str(e),
            "current_step": "analyze_jd",
            "analysis_log": logs,
        }


def node_retrieve_projects(state: WorkflowState) -> dict:
    """按文档类型从各自的向量数据库中分别 RAG 检索。"""
    logs = list(state.get("analysis_log") or [])
    logs.append("[6/8] RAG 分类检索个人材料...")

    jd_analysis = state.get("jd_analysis", {})
    keywords = jd_analysis.get("keywords", [])
    tech_stack = jd_analysis.get("tech_stack", [])
    query = "，".join(keywords + tech_stack) if (keywords or tech_stack) else state["jd_text"][:200]

    # 检查哪些类型有入库文档
    parsed_docs = state.get("parsed_docs") or []
    available_types = {d["doc_type"] for d in parsed_docs} & set(RAG_DOC_TYPES)

    matched_sections: dict[str, list] = {}

    for doc_type in RAG_DOC_TYPES:
        if doc_type not in available_types:
            continue

        try:
            results = retrieve(
                query=query,
                top_k=10,
                rerank_top_n=5,
                collection_name=_collection_name(doc_type),
            )
            if results:
                matched_sections[doc_type] = results
                logs.append(f"  → {doc_type}: 检索到 {len(results)} 条片段")
                for i, res in enumerate(results):
                    logs.append(f"    [{i+1}] {res['metadata'].get('source_file', '未知')}: {res['text'][:80]}...")
            else:
                logs.append(f"  → {doc_type}: 无匹配结果")
        except Exception as e:
            logs.append(f"  ✗ {doc_type} 检索失败: {e}")

    total = sum(len(v) for v in matched_sections.values())
    logs.append(f"  ✓ 共检索到 {total} 条相关片段，覆盖 {len(matched_sections)} 个类型")

    return {
        "matched_sections": matched_sections,
        "current_step": "retrieve_projects",
        "analysis_log": logs,
    }


def _build_section_context(matched_sections: dict) -> dict[str, str]:
    """将各类型的检索结果组装为分类文本。"""
    section_contexts = {}
    for doc_type, results in matched_sections.items():
        if results:
            section_contexts[doc_type] = "\n\n".join(r["text"] for r in results)
    return section_contexts


def node_generate_resume(state: WorkflowState) -> dict:
    """简历生成节点。根据 JD 分析、按类型 RAG 检索结果和个人基本信息生成结构化简历数据，再通过模板渲染。"""
    logs = list(state.get("analysis_log") or [])
    logs.append("[7/8] 生成定制化简历...")

    jd_analysis = state.get("jd_analysis", {})
    matched_sections = state.get("matched_sections") or {}
    section_contexts = _build_section_context(matched_sections)
    profile = state.get("profile")

    try:
        # 1. LLM 生成结构化简历数据（JSON dict）
        resume_data = generate_resume(
            jd_analysis=jd_analysis,
            section_contexts=section_contexts,
            profile=profile,
        )
        logs.append("  ✓ 简历结构化数据生成完成")

        # 2. 通过模板渲染为 Markdown
        template_path = state.get("template_path", "./templates/default.md")
        if "_raw_markdown" in resume_data:
            # 旧路径兼容：直接使用原始 Markdown
            resume_md = resume_data["_raw_markdown"]
        else:
            resume_md = render_resume(template_path, resume_data)
        logs.append("  ✓ 模板渲染完成")

        return {
            "resume_data": resume_data,
            "resume_draft": resume_md,
            "current_step": "generate_resume",
            "analysis_log": logs,
        }
    except Exception as e:
        logs.append(f"  ✗ 简历生成失败: {e}")
        return {
            "error": str(e),
            "current_step": "generate_resume",
            "analysis_log": logs,
        }


def node_self_check(state: WorkflowState) -> dict:
    """简历自检节点 — Reflection。根据 JD 分析结果对生成的简历草稿进行自检和改进。"""
    logs = list(state.get("analysis_log") or [])
    logs.append("[8/8] 简历自检 (Reflection)...")

    jd_analysis = state.get("jd_analysis", {})
    resume = state.get("resume_draft", "")

    try:
        check = self_check_resume(jd_analysis, resume)
        passed = check.get("pass", False)
        score = check.get("coverage_score", "N/A")
        logs.append(f"  → 覆盖度: {score}, 通过: {passed}")

        return {
            "resume_final": resume,
            "current_step": "self_check",
            "analysis_log": logs,
        }
    except Exception as e:
        logs.append(f"  ✗ 自检失败，直接使用草稿: {e}")
        return {
            "resume_final": resume,
            "current_step": "self_check",
            "analysis_log": logs,
        }


def node_save_output(state: WorkflowState) -> dict:
    """保存最终输出文件。"""
    logs = list(state.get("analysis_log") or [])

    resume_content = state.get("resume_final") or state.get("resume_draft", "")
    if not resume_content:
        logs.append("[输出] 无简历内容可保存")
        return {"analysis_log": logs}

    # 保存简历 Markdown
    resume_path = save_output(resume_content, "./output/resume.md")
    logs.append(f"[输出] 简历已保存: {resume_path}")

    # 保存简历结构化数据（JSON）
    resume_data = state.get("resume_data")
    if resume_data and "_raw_markdown" not in resume_data:
        resume_json = json.dumps(resume_data, ensure_ascii=False, indent=2)
        json_path = save_output(resume_json, "./output/resume_data.json")
        logs.append(f"[输出] 简历结构化数据已保存: {json_path}")

    # 保存 JD 分析报告
    jd_analysis = state.get("jd_analysis")
    if jd_analysis:
        report = json.dumps(jd_analysis, ensure_ascii=False, indent=2)
        report_path = save_output(report, "./output/jd_analysis.json")
        logs.append(f"[输出] JD 分析报告已保存: {report_path}")

    # 保存过程日志
    log_content = "\n".join(logs)
    log_path = save_output(log_content, "./output/analysis_log.txt")
    logs.append(f"[输出] 过程日志已保存: {log_path}")

    return {
        "resume_file": resume_path,
        "current_step": "done",
        "analysis_log": logs,
    }


# ============================================================
# 构建 LangGraph 状态图
# ============================================================

def build_graph() -> StateGraph:
    """构建并返回工作流状态图。

    流程: parse_docs → classify_docs → extract_profile → build_index → analyze_jd → retrieve → generate → self_check → save
    """
    graph = StateGraph(WorkflowState)

    # 添加节点
    graph.add_node("parse_documents", node_parse_documents)
    graph.add_node("classify_documents", node_classify_documents)
    graph.add_node("extract_profile", node_extract_profile)
    graph.add_node("build_index", node_build_index)
    graph.add_node("analyze_jd", node_analyze_jd)
    graph.add_node("retrieve_projects", node_retrieve_projects)
    graph.add_node("generate_resume", node_generate_resume)
    graph.add_node("self_check", node_self_check)
    graph.add_node("save_output", node_save_output)

    # 设置入口
    graph.set_entry_point("parse_documents")

    # 连接边
    graph.add_edge("parse_documents", "classify_documents")
    graph.add_edge("classify_documents", "extract_profile")
    graph.add_edge("extract_profile", "build_index")
    graph.add_edge("build_index", "analyze_jd")
    graph.add_edge("analyze_jd", "retrieve_projects")
    graph.add_edge("retrieve_projects", "generate_resume")
    graph.add_edge("generate_resume", "self_check")
    graph.add_edge("self_check", "save_output")
    graph.add_edge("save_output", END)

    return graph


def run_pipeline(
    jd_text: str,
    personal_docs: list[str],
    template_path: str = "./templates/default.md",
) -> WorkflowState:
    """运行完整的 MVP Pipeline。

    Args:
        jd_text: JD 文本内容
        personal_docs: 个人材料文件路径列表
        template_path: 简历模板路径

    Returns:
        最终的 WorkflowState
    """
    graph = build_graph()
    app = graph.compile()

    initial_state: WorkflowState = {
        "jd_text": jd_text,
        "personal_docs": personal_docs,
        "template_path": template_path,
        "parsed_docs": None,
        "profile": None,
        "jd_analysis": None,
        "matched_sections": None,
        "resume_data": None,
        "resume_draft": None,
        "resume_final": None,
        "resume_file": None,
        "interview_qa": None,
        "analysis_log": [],
        "current_step": "start",
        "error": None,
    }

    final_state = app.invoke(initial_state)
    return final_state
