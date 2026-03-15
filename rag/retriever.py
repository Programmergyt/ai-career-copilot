"""RAG 检索模块 — 向量检索 + Rerank"""

from langchain_community.vectorstores import Chroma
from langchain_community.document_compressors.dashscope_rerank import DashScopeRerank

from rag.embeddings import get_embedding_model
from config_loader import get_rerank_config, get_vector_store_config


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
        rerank_cfg = get_rerank_config()
        rerank_kwargs = {"model": rerank_cfg["model"]}
        if rerank_cfg["api_key"]:
            rerank_kwargs["dashscope_api_key"] = rerank_cfg["api_key"]
        reranker = DashScopeRerank(**rerank_kwargs)
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
