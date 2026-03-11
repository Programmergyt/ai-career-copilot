"""RAG 检索模块 — 向量检索 + Rerank"""

import os
from langchain_community.vectorstores import Chroma
from langchain_community.document_compressors.dashscope_rerank import DashScopeRerank

from rag.embeddings import get_embedding_model


def get_vectorstore(
    collection_name: str = "personal_knowledge",
    persist_directory: str | None = None,
) -> Chroma:
    """获取已有的 Chroma 向量库实例。"""
    if persist_directory is None:
        persist_directory = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embedding_model(),
        persist_directory=persist_directory,
    )


def retrieve(
    query: str,
    top_k: int = 10,
    rerank_top_n: int = 5,
    collection_name: str = "personal_knowledge",
    persist_directory: str | None = None,
) -> list[dict]:
    """语义检索 + Rerank，返回最相关的文档片段。

    Returns:
        [{"text": str, "score": float, "metadata": dict}, ...]
    """
    vectorstore = get_vectorstore(collection_name, persist_directory)

    # 第一步：向量检索 TopK
    results = vectorstore.similarity_search_with_score(query, k=top_k)
    if not results:
        return []

    documents = [doc.page_content for doc, _score in results]
    metas = [doc.metadata for doc, _score in results]

    # 第二步：Rerank
    try:
        reranker = DashScopeRerank(
            model=os.getenv("RERANK_MODEL", "gte-rerank-v2"),
        )
        rerank_results = reranker.rerank(
            documents=documents,
            query=query,
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
