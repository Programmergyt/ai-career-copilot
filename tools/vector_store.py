"""ChromaDB 向量存储封装"""

import os
from chromadb import PersistentClient
from chromadb.config import Settings


def get_chroma_client(persist_dir: str | None = None) -> PersistentClient:
    """获取 ChromaDB 持久化客户端。"""
    if persist_dir is None:
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
    os.makedirs(persist_dir, exist_ok=True)
    return PersistentClient(
        path=persist_dir,
        settings=Settings(anonymized_telemetry=False),
    )
