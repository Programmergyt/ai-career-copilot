"""Embedding 模型封装"""

import os
from langchain_community.embeddings import DashScopeEmbeddings


def get_embedding_model() -> DashScopeEmbeddings:
    """返回 DashScope Embedding 实例。

    需要环境变量 DASHSCOPE_API_KEY。
    """
    return DashScopeEmbeddings(model=os.getenv("EMBEDDING_MODEL", "text-embedding-v4"))
