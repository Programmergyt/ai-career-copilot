"""RAG 检索模块 — 向量检索 + Cross-Encoder Rerank（带 JD）"""

from langchain_community.vectorstores import Chroma
from langchain_community.document_compressors.dashscope_rerank import DashScopeRerank

from rag.embeddings import get_embedding_model
from config_loader import get_rerank_config, get_vector_store_config, get_rag_config


def get_vectorstore(
    collection_name: str = "personal_knowledge",
    persist_directory: str | None = None,
) -> Chroma:
    """获取已有的 Chroma 向量库实例。"""
    if persist_directory is None:
        persist_directory = get_vector_store_config()["persist_directory"]
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embedding_model(),
        persist_directory=persist_directory,
    )


def retrieve(
    query: str,
    top_k: int | None = None,
    rerank_top_n: int | None = None,
    jd_text: str | None = None,
    collection_name: str = "personal_knowledge",
    persist_directory: str | None = None,
) -> list[dict]:
    """语义检索 + Cross-Encoder Rerank（带 JD 上下文）。

    Flow:
        Step 1: Embedding Recall (top_k=20)
        Step 2: Cross-Encoder Rerank（使用 JD 全文作为 query 以提高相关性）
        Step 3: 取 top 5

    Args:
        query: 用于 embedding 检索的关键词 query
        top_k: embedding 召回数量，默认从 config.yaml 读取 (20)
        rerank_top_n: rerank 后保留数量，默认从 config.yaml 读取 (5)
        jd_text: JD 原文，用于 cross-encoder rerank 的 query（更精准）
        collection_name: 向量库 collection 名称
        persist_directory: 向量库路径

    Returns:
        [{"text": str, "score": float, "metadata": dict}, ...]
    """
    rag_cfg = get_rag_config()
    if top_k is None:
        top_k = rag_cfg.get("search_top_k", 20)
    if rerank_top_n is None:
        rerank_top_n = rag_cfg.get("rerank_top_n", 5)

    vectorstore = get_vectorstore(collection_name, persist_directory)

    # Step 1: Embedding Recall top_k
    results = vectorstore.similarity_search_with_score(query, k=top_k)
    if not results:
        return []

    documents = [doc.page_content for doc, _score in results]
    metas = [doc.metadata for doc, _score in results]

    # Step 2: Cross-Encoder Rerank（带 JD 全文以提高匹配精度）
    rerank_query = jd_text if jd_text else query

    try:
        rerank_cfg = get_rerank_config()
        rerank_kwargs = {"model": rerank_cfg["model"]}
        if rerank_cfg["api_key"]:
            rerank_kwargs["dashscope_api_key"] = rerank_cfg["api_key"]
        reranker = DashScopeRerank(**rerank_kwargs)

        # Step 3: 取 top_n
        rerank_results = reranker.rerank(
            documents=documents,
            query=rerank_query,
            top_n=rerank_top_n,
        )
        ranked = [
            {
                "text": documents[item["index"]],
                "score": item["relevance_score"],
                "metadata": metas[item["index"]],
            }
            for item in rerank_results
        ]
    except Exception:
        # Rerank 不可用时，退化为纯向量检索结果
        ranked = [
            {
                "text": documents[i],
                "score": float(score),
                "metadata": metas[i],
            }
            for i, (doc, score) in enumerate(results[:rerank_top_n])
        ]

    return ranked
