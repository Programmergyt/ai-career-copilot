"""LangGraph 工作流编排 — 串联 JD 分析 → 简历生成 MVP Pipeline"""

import json
from langgraph.graph import StateGraph, END

from workflow.state import WorkflowState
from tools.file_parser import parse_file, parse_directory
from rag.indexer import build_index
from rag.retriever import retrieve
from agents.jd_analyzer import analyze_jd
from agents.resume_writer import generate_resume, self_check_resume
from tools.template_renderer import save_output


# ============================================================
# 节点函数：每个节点接收并返回 WorkflowState
# ============================================================

def node_parse_documents(state: WorkflowState) -> dict:
    """解析并入库个人材料文档。"""
    logs = list(state.get("analysis_log") or [])
    logs.append("[1/5] 开始解析个人材料文档...")

    texts, metas = [], []
    for fpath in state["personal_docs"]:
        from pathlib import Path
        p = Path(fpath)
        if p.is_dir():
            # 递归解析目录下所有支持的文件
            dir_results = parse_directory(fpath)
            for sub_path, text in dir_results.items():
                if text.startswith("[解析失败]"):
                    logs.append(f"  ✗ 解析失败: {sub_path} — {text}")
                else:
                    texts.append(text)
                    metas.append({"source_file": sub_path, "doc_type": "personal"})
                    logs.append(f"  ✓ 解析成功: {sub_path}")
        else:
            try:
                text = parse_file(fpath)
                texts.append(text)
                metas.append({"source_file": fpath, "doc_type": "personal"})
                logs.append(f"  ✓ 解析成功: {fpath}")
            except Exception as e:
                logs.append(f"  ✗ 解析失败: {fpath} — {e}")

    if texts:
        try:
            build_index(texts=texts, metadatas=metas)
            logs.append(f"  → 成功入库 {len(texts)} 份文档")
        except Exception as e:
            logs.append(f"  → 入库失败: {e}")
    else:
        logs.append("  → 无可入库文档")

    return {
        "current_step": "parse_documents",
        "analysis_log": logs,
    }


def node_analyze_jd(state: WorkflowState) -> dict:
    """JD 分析节点。"""
    logs = list(state.get("analysis_log") or [])
    logs.append("[2/5] 开始分析 JD...")

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
    """RAG 检索与 JD 匹配的个人项目片段。"""
    logs = list(state.get("analysis_log") or [])
    logs.append("[3/5] RAG 检索个人材料...")

    jd_analysis = state.get("jd_analysis", {})
    keywords = jd_analysis.get("keywords", [])
    tech_stack = jd_analysis.get("tech_stack", [])
    query = "，".join(keywords + tech_stack) if (keywords or tech_stack) else state["jd_text"][:200]

    try:
        results = retrieve(query=query, top_k=10, rerank_top_n=5)
        logs.append(f"  ✓ 检索到 {len(results)} 条相关片段")
        return {
            "matched_projects": results,
            "current_step": "retrieve_projects",
            "analysis_log": logs,
        }
    except Exception as e:
        logs.append(f"  ✗ RAG 检索失败: {e}")
        return {
            "matched_projects": [],
            "current_step": "retrieve_projects",
            "analysis_log": logs,
        }


def node_generate_resume(state: WorkflowState) -> dict:
    """简历生成节点。"""
    logs = list(state.get("analysis_log") or [])
    logs.append("[4/5] 生成定制化简历...")

    jd_analysis = state.get("jd_analysis", {})
    matched = state.get("matched_projects") or []
    personal_context = "\n\n".join(r["text"] for r in matched) if matched else None

    try:
        resume_md = generate_resume(
            jd_analysis=jd_analysis,
            personal_context=personal_context,
        )
        logs.append("  ✓ 简历草稿生成完成")
        return {
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
    """简历自检节点 — Reflection。"""
    logs = list(state.get("analysis_log") or [])
    logs.append("[5/5] 简历自检 (Reflection)...")

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
    """构建并返回 MVP 工作流状态图。

    流程: parse_docs → analyze_jd → retrieve → generate → self_check → save
    """
    graph = StateGraph(WorkflowState)

    # 添加节点
    graph.add_node("parse_documents", node_parse_documents)
    graph.add_node("analyze_jd", node_analyze_jd)
    graph.add_node("retrieve_projects", node_retrieve_projects)
    graph.add_node("generate_resume", node_generate_resume)
    graph.add_node("self_check", node_self_check)
    graph.add_node("save_output", node_save_output)

    # 设置入口
    graph.set_entry_point("parse_documents")

    # 连接边
    graph.add_edge("parse_documents", "analyze_jd")
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
        "jd_analysis": None,
        "matched_projects": None,
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
