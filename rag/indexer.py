"""文档入库 — 将文本分块后写入 ChromaDB 向量数据库"""

import os
import uuid
from langchain_text_splitters  import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma

from rag.embeddings import get_embedding_model


def build_index(
    texts: list[str],
    metadatas: list[dict] | None = None,
    collection_name: str = "personal_knowledge",
    persist_directory: str | None = None,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> Chroma:
    """将文本列表分块后写入 ChromaDB，返回 Chroma 向量库实例。"""
    if persist_directory is None:
        persist_directory = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n## ", "\n### ", "\n\n", "\n", "。", "；", " "],
    )

    all_chunks: list[str] = []
    all_metas: list[dict] = []

    for i, text in enumerate(texts):
        meta = metadatas[i] if metadatas else {}
        chunks = splitter.split_text(text)
        for ci, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_metas.append({**meta, "chunk_index": ci})

    if not all_chunks:
        raise ValueError("没有可入库的文本块")

    embeddings = get_embedding_model()

    ids = [str(uuid.uuid4()) for _ in all_chunks]

    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_directory,
    )
    vectorstore.add_texts(texts=all_chunks, metadatas=all_metas, ids=ids)
    return vectorstore
