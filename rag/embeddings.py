"""Embedding 模型封装"""

from langchain_community.embeddings import DashScopeEmbeddings

from config_loader import get_embedding_config


def get_embedding_model() -> DashScopeEmbeddings:
    """返回 DashScope Embedding 实例，模型与 API Key 由 config.yaml 配置。"""
    cfg = get_embedding_config()
    kwargs = {"model": cfg["model"]}
    if cfg["api_key"]:
        kwargs["dashscope_api_key"] = cfg["api_key"]
    return DashScopeEmbeddings(**kwargs)
