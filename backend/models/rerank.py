"""Rerank 统一封装：基于 config.yaml 的 provider 动态创建 reranker。"""

import asyncio
from typing import Any

from config_loader import get_rerank_config


class _HuggingFaceCrossEncoderReranker:
    """本地 CrossEncoder 适配为统一 rerank 输出格式。"""

    def __init__(self, model_name: str):
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model_name)

    def rerank(self, documents: list[str], query: str, top_n: int) -> list[dict]:
        pairs = [(query, doc) for doc in documents]
        scores = self._model.predict(pairs)
        ranked = sorted(
            (
                {"index": i, "relevance_score": float(score)}
                for i, score in enumerate(scores)
            ),
            key=lambda item: item["relevance_score"],
            reverse=True,
        )
        return ranked[:top_n]


class _CohereRerankerAdapter:
    """将 Cohere 文档压缩器适配为统一 rerank 接口。"""

    def __init__(self, model_name: str, api_key: str, top_n: int):
        from langchain_cohere import CohereRerank

        self._compressor = CohereRerank(
            model=model_name,
            cohere_api_key=api_key,
            top_n=top_n,
        )

    def rerank(self, documents: list[str], query: str, top_n: int) -> list[dict]:
        from langchain_core.documents import Document

        docs = [Document(page_content=text, metadata={"index": i}) for i, text in enumerate(documents)]
        reranked_docs = self._compressor.compress_documents(docs, query)

        results = []
        for doc in reranked_docs[:top_n]:
            idx = doc.metadata.get("index")
            if idx is None:
                continue
            score = doc.metadata.get("relevance_score", doc.metadata.get("score", 0.0))
            results.append({"index": int(idx), "relevance_score": float(score)})
        return results


def _normalize_provider(provider: str) -> str:
    return (provider or "dashscope").strip().lower()


def get_reranker() -> Any:
    """根据 rerank.provider 返回对应 reranker 对象。"""
    cfg = get_rerank_config()
    provider = _normalize_provider(cfg.get("provider", "dashscope"))

    if provider in {"dashscope", "tongyi"}:
        from langchain_community.document_compressors.dashscope_rerank import DashScopeRerank

        kwargs = {"model": cfg["model"]}
        if cfg.get("api_key"):
            kwargs["dashscope_api_key"] = cfg["api_key"]
        return DashScopeRerank(**kwargs)

    if provider in {"cohere"}:
        if not cfg.get("api_key"):
            raise ValueError("rerank.provider=cohere requires api_key_env in config.")
        return _CohereRerankerAdapter(cfg["model"], cfg["api_key"], int(cfg.get("top_n", 5)))

    if provider in {"huggingface", "hf", "sentence_transformers", "local"}:
        return _HuggingFaceCrossEncoderReranker(cfg["model"])

    raise ValueError(
        "Unsupported rerank.provider='{}'. Supported providers: dashscope, cohere, huggingface".format(
            provider
        )
    )


def _normalize_rerank_results(raw_results: Any, top_n: int) -> list[dict]:
    normalized: list[dict] = []
    if not isinstance(raw_results, list):
        return normalized

    for idx, item in enumerate(raw_results):
        if isinstance(item, dict):
            doc_idx = item.get("index", item.get("document_index", idx))
            score = item.get("relevance_score", item.get("score", 0.0))
        else:
            doc_idx = getattr(item, "index", idx)
            score = getattr(item, "relevance_score", getattr(item, "score", 0.0))

        try:
            normalized.append({
                "index": int(doc_idx),
                "relevance_score": float(score),
            })
        except (TypeError, ValueError):
            continue

    normalized.sort(key=lambda x: x["relevance_score"], reverse=True)
    return normalized[:top_n]


def rerank_texts(documents: list[str], query: str, top_n: int | None = None) -> list[dict]:
    """对文本列表执行 rerank，返回统一格式结果。"""
    cfg = get_rerank_config()
    if top_n is None:
        top_n = int(cfg.get("top_n", 5))

    reranker = get_reranker()
    raw_results = reranker.rerank(
        documents=documents,
        query=query,
        top_n=top_n,
    )
    return _normalize_rerank_results(raw_results, top_n)


async def arerank_texts(documents: list[str], query: str, top_n: int | None = None) -> list[dict]:
    """异步对文本列表执行 rerank，返回统一格式结果。"""
    return await asyncio.to_thread(rerank_texts, documents, query, top_n)
