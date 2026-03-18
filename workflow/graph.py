"""LangGraph 工作流编排 — 串联 JD 分析 → 简历生成 Pipeline

流程:
  parse_docs → analyze_jd → classify_docs → extract_profile
  → refine_skills → build_index → retrieve → generate → self_check → save
"""

import json
from langgraph.graph import StateGraph, END

from workflow.state import WorkflowState
from tools.file_parser import parse_file, parse_directory
from rag.indexer import build_index
from rag.retriever import retrieve
from agents.jd_analyzer import analyze_jd
from agents.resume_writer import generate_resume, self_check_resume
from agents.doc_classifier import classify_documents, extract_profile, refine_skill_documents
from agents.llm import call_llm
from tools.template_renderer import save_output, render_resume
from prompts.jd_analysis import MATCH_EXPLANATION_SYSTEM, MATCH_EXPLANATION_USER


# ============================================================
# 实时日志工具
# ============================================================

def _log(msg: str, logs: list[str]) -> None:
    """即时输出日志到控制台并记录到日志列表。"""
    print(msg, flush=True)
    logs.append(msg)


# ============================================================
# 节点函数：每个节点接收并返回 WorkflowState
# ============================================================

def node_parse_documents(state: WorkflowState) -> dict:
    """解析个人材料文档（仅解析，不入库）。"""
    logs = list(state.get("analysis_log") or [])
    _log("[1/10] 开始解析个人材料文档...", logs)

    parsed_docs = []
    for fpath in state["personal_docs"]:
        from pathlib import Path
        p = Path(fpath)
        if p.is_dir():
            dir_results = parse_directory(fpath)
            for sub_path, text in dir_results.items():
                if text.startswith("[解析失败]"):
                    _log(f"  ✗ 解析失败: {sub_path} — {text}", logs)
                else:
                    parsed_docs.append({
                        "text": text,
                        "source_file": sub_path,
                        "doc_type": "personal",
                    })
                    _log(f"  ✓ 解析成功: {sub_path}", logs)
        else:
            try:
                text = parse_file(fpath)
                parsed_docs.append({
                    "text": text,
                    "source_file": fpath,
                    "doc_type": "personal",
                })
                _log(f"  ✓ 解析成功: {fpath}", logs)
            except Exception as e:
                _log(f"  ✗ 解析失败: {fpath} — {e}", logs)

    _log(f"  → 共解析 {len(parsed_docs)} 份文档", logs)

    return {
        "parsed_docs": parsed_docs,
        "current_step": "parse_documents",
        "analysis_log": logs,
    }


def node_analyze_jd(state: WorkflowState) -> dict:
    """JD 分析节点（提前到第 2 步，为后续分类和提炼提供依据）。"""
    logs = list(state.get("analysis_log") or [])
    _log("[2/10] 开始分析 JD...", logs)

    try:
        jd_analysis = analyze_jd(state["jd_text"])
        _log("  ✓ JD 分析完成", logs)
        _log(f"  → 岗位: {jd_analysis.get('position_title', '未知')}", logs)
        _log(f"  → 技术栈: {jd_analysis.get('tech_stack', [])}", logs)
        _log(f"  → 关键词: {jd_analysis.get('keywords', [])}", logs)
        return {
            "jd_analysis": jd_analysis,
            "current_step": "analyze_jd",
            "analysis_log": logs,
        }
    except Exception as e:
        _log(f"  ✗ JD 分析失败: {e}", logs)
        return {
            "error": str(e),
            "current_step": "analyze_jd",
            "analysis_log": logs,
        }


def node_classify_documents(state: WorkflowState) -> dict:
    """使用 LLM 对文档进行分类（个人信息/项目经历/实习经历/专业技能/论文成果）。"""
    logs = list(state.get("analysis_log") or [])
    _log("[3/10] 文档分类中...", logs)

    parsed_docs = list(state.get("parsed_docs") or [])
    if not parsed_docs:
        _log("  → 无文档可分类", logs)
        return {"parsed_docs": parsed_docs, "current_step": "classify_documents", "analysis_log": logs}

    try:
        parsed_docs = classify_documents(parsed_docs)
        type_counts = {}
        for doc in parsed_docs:
            t = doc["doc_type"]
            type_counts[t] = type_counts.get(t, 0) + 1
        for t, cnt in type_counts.items():
            _log(f"  → {t}: {cnt} 份", logs)
        _log("  ✓ 文档分类完成", logs)
    except Exception as e:
        _log(f"  ✗ 文档分类失败: {e}", logs)

    return {
        "parsed_docs": parsed_docs,
        "current_step": "classify_documents",
        "analysis_log": logs,
    }


def node_extract_profile(state: WorkflowState) -> dict:
    """从 profile 类型文档中提取个人基本信息。"""
    logs = list(state.get("analysis_log") or [])
    _log("[4/10] 提取个人基本信息...", logs)

    parsed_docs = state.get("parsed_docs") or []
    profile = None

    try:
        profile = extract_profile(parsed_docs)
        if profile and not profile.get("parse_error"):
            _log(f"  ✓ 提取成功 — 姓名: {profile.get('name', '未知')}", logs)
        elif profile:
            _log("  ⚠ 信息提取结果解析异常，使用原始文本", logs)
        else:
            _log("  → 未找到 个人信息 类型文档，跳过提取", logs)
    except Exception as e:
        _log(f"  ✗ 提取失败: {e}", logs)

    return {
        "profile": profile,
        "current_step": "extract_profile",
        "analysis_log": logs,
    }


def node_refine_skills(state: WorkflowState) -> dict:
    """对「专业技能」类文档进行 LLM 提炼，只保留与 JD 相关的内容后再入库。"""
    logs = list(state.get("analysis_log") or [])
    _log("[5/10] 技能材料提炼（针对 JD 筛选）...", logs)

    parsed_docs = list(state.get("parsed_docs") or [])
    jd_analysis = state.get("jd_analysis") or {}

    skill_docs = [d for d in parsed_docs if d.get("doc_type") == "专业技能"]
    if not skill_docs:
        _log("  → 无专业技能文档，跳过提炼", logs)
        return {"parsed_docs": parsed_docs, "current_step": "refine_skills", "analysis_log": logs}

    if not jd_analysis:
        _log("  → JD 分析结果为空，跳过提炼", logs)
        return {"parsed_docs": parsed_docs, "current_step": "refine_skills", "analysis_log": logs}

    try:
        parsed_docs = refine_skill_documents(parsed_docs, jd_analysis)
        refined_count = sum(1 for d in parsed_docs if d.get("text_original"))
        _log(f"  ✓ 已提炼 {refined_count} 份技能文档", logs)
    except Exception as e:
        _log(f"  ✗ 技能提炼失败，使用原始文本: {e}", logs)

    return {
        "parsed_docs": parsed_docs,
        "current_step": "refine_skills",
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
    _log("[6/10] 构建 RAG 向量索引（按类型分库）...", logs)

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
            _log(f"  → {doc_type}: 成功入库 {len(texts)} 份文档", logs)
            total_indexed += len(texts)
        except Exception as e:
            _log(f"  → {doc_type}: 入库失败: {e}", logs)

    if total_indexed == 0:
        _log("  → 无文档可入库", logs)

    return {
        "current_step": "build_index",
        "analysis_log": logs,
    }


def _explain_match_reasons(
    jd_analysis: dict,
    doc_type: str,
    results: list[dict],
) -> str:
    """使用 LLM 为检索到的材料生成匹配原因说明。"""
    position = jd_analysis.get("position_title", "目标岗位")
    tech_stack = ", ".join(jd_analysis.get("tech_stack", []))
    requirements = ", ".join(jd_analysis.get("keywords", [])[:5])

    items_text = ""
    for i, res in enumerate(results):
        source = res["metadata"].get("source_file", "未知")
        score = res.get("score", 0)
        snippet = res["text"][:200]
        items_text += f"\n{i+1}. [匹配度: {score:.3f}] 来源: {source}\n   内容: {snippet}...\n"

    prompt = MATCH_EXPLANATION_USER.format(
        position=position,
        tech_stack=tech_stack,
        requirements=requirements,
        doc_type=doc_type,
        items=items_text,
    )

    try:
        return call_llm(MATCH_EXPLANATION_SYSTEM, prompt)
    except Exception:
        return ""


def node_retrieve_projects(state: WorkflowState) -> dict:
    """按文档类型从各自的向量数据库中分别 RAG 检索（带 JD 的 cross-encoder rerank）。"""
    logs = list(state.get("analysis_log") or [])
    _log("[7/10] RAG 分类检索个人材料（embedding recall → cross-encoder rerank）...", logs)

    jd_analysis = state.get("jd_analysis", {})
    jd_text = state.get("jd_text", "")
    keywords = jd_analysis.get("keywords", [])
    tech_stack = jd_analysis.get("tech_stack", [])
    query = "，".join(keywords + tech_stack) if (keywords or tech_stack) else jd_text[:200]

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
                jd_text=jd_text,  # 将 JD 全文传给 cross-encoder rerank
                collection_name=_collection_name(doc_type),
            )
            if results:
                matched_sections[doc_type] = results
                _log(f"  → {doc_type}: 检索到 {len(results)} 条片段", logs)
                for i, res in enumerate(results):
                    source = res['metadata'].get('source_file', '未知')
                    score = res.get('score', 0)
                    _log(f"    [{i+1}] 匹配度: {score:.3f} | 来源: {source}", logs)
                    _log(f"        摘要: {res['text'][:80]}...", logs)

                # 使用 LLM 生成详细的匹配原因
                _log(f"  → {doc_type} 匹配原因分析:", logs)
                explanation = _explain_match_reasons(jd_analysis, doc_type, results)
                if explanation:
                    for line in explanation.strip().split("\n"):
                        if line.strip():
                            _log(f"    {line.strip()}", logs)
            else:
                _log(f"  → {doc_type}: 无匹配结果", logs)
        except Exception as e:
            _log(f"  ✗ {doc_type} 检索失败: {e}", logs)

    total = sum(len(v) for v in matched_sections.values())
    _log(f"  ✓ 共检索到 {total} 条相关片段，覆盖 {len(matched_sections)} 个类型", logs)

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
    _log("[8/10] 生成定制化简历...", logs)

    jd_analysis = state.get("jd_analysis", {})
    matched_sections = state.get("matched_sections") or {}
    section_contexts = _build_section_context(matched_sections)
    profile = state.get("profile")

    try:
        # 1. LLM 生成结构化简历数据（JSON dict），不同版块独立生成，LLM 只看到该版块的材料和 JD 分析结果
        resume_data = generate_resume(
            jd_analysis=jd_analysis,
            section_contexts=section_contexts,
            profile=profile,
        )
        _log("  ✓ 简历结构化数据生成完成", logs)

        # 2. 通过模板渲染为 Markdown
        template_path = state.get("template_path", "./templates/default.md")
        resume_md = render_resume(template_path, resume_data)
        _log("  ✓ 模板渲染完成", logs)

        return {
            "resume_data": resume_data,
            "resume_draft": resume_md,
            "current_step": "generate_resume",
            "analysis_log": logs,
        }
    except Exception as e:
        _log(f"  ✗ 简历生成失败: {e}", logs)
        return {
            "error": str(e),
            "current_step": "generate_resume",
            "analysis_log": logs,
        }


def node_self_check(state: WorkflowState) -> dict:
    """简历自检节点 — Reflection。根据 JD 分析结果对生成的简历草稿进行自检和改进。"""
    logs = list(state.get("analysis_log") or [])
    _log("[9/10] 简历自检 (Reflection)...", logs)

    jd_analysis = state.get("jd_analysis", {})
    resume = state.get("resume_draft", "")

    try:
        check = self_check_resume(jd_analysis, resume)
        passed = check.get("pass", False)
        score = check.get("coverage_score", "N/A")
        _log(f"  → 覆盖度: {score}, 通过: {passed}", logs)

        if check.get("missing_requirements"):
            _log(f"  → 未覆盖: {check['missing_requirements']}", logs)

        return {
            "resume_final": resume,
            "current_step": "self_check",
            "analysis_log": logs,
        }
    except Exception as e:
        _log(f"  ✗ 自检失败，直接使用草稿: {e}", logs)
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
        _log("[输出] 无简历内容可保存", logs)
        return {"analysis_log": logs}

    # 保存简历 Markdown
    resume_path = save_output(resume_content, "./output/resume.md")
    _log(f"[输出] 简历已保存: {resume_path}", logs)

    # 保存简历结构化数据（JSON）
    resume_data = state.get("resume_data")
    if resume_data:
        resume_json = json.dumps(resume_data, ensure_ascii=False, indent=2)
        json_path = save_output(resume_json, "./output/resume_data.json")
        _log(f"[输出] 简历结构化数据已保存: {json_path}", logs)

    # 保存 JD 分析报告
    jd_analysis = state.get("jd_analysis")
    if jd_analysis:
        report = json.dumps(jd_analysis, ensure_ascii=False, indent=2)
        report_path = save_output(report, "./output/jd_analysis.json")
        _log(f"[输出] JD 分析报告已保存: {report_path}", logs)

    # 保存过程日志
    log_content = "\n".join(logs)
    log_path = save_output(log_content, "./output/analysis_log.txt")
    _log(f"[输出] 过程日志已保存: {log_path}", logs)

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

    流程:
      parse_docs → analyze_jd → classify_docs → extract_profile
      → refine_skills → build_index → retrieve → generate → self_check → save
    """
    graph = StateGraph(WorkflowState)

    # 添加节点
    graph.add_node("parse_documents", node_parse_documents)
    graph.add_node("analyze_jd", node_analyze_jd)
    graph.add_node("classify_documents", node_classify_documents)
    graph.add_node("extract_profile", node_extract_profile)
    graph.add_node("refine_skills", node_refine_skills)
    graph.add_node("build_index", node_build_index)
    graph.add_node("retrieve_projects", node_retrieve_projects)
    graph.add_node("generate_resume", node_generate_resume)
    graph.add_node("self_check", node_self_check)
    graph.add_node("save_output", node_save_output)

    # 设置入口
    graph.set_entry_point("parse_documents")

    # 连接边: parse → analyze_jd → classify → extract_profile → refine → build → retrieve → generate → check → save
    graph.add_edge("parse_documents", "analyze_jd")
    graph.add_edge("analyze_jd", "classify_documents")
    graph.add_edge("classify_documents", "extract_profile")
    graph.add_edge("extract_profile", "refine_skills")
    graph.add_edge("refine_skills", "build_index")
    graph.add_edge("build_index", "retrieve_projects")
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
    """运行完整的 Pipeline。

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
