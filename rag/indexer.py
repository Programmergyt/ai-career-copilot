"""文档入库 — 将文本分块后写入 ChromaDB 向量数据库"""

import hashlib
from langchain_text_splitters  import RecursiveCharacterTextSplitter,MarkdownHeaderTextSplitter
from langchain_community.vectorstores import Chroma

from rag.embeddings import get_embedding_model
from config_loader import get_vector_store_config, get_rag_config


def build_index(
    texts: list[str],
    metadatas: list[dict] | None = None,
    collection_name: str = "personal_knowledge",
    persist_directory: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
):
    """
    构建向量索引（RAG indexer）

    处理流程：
    1. Markdown标题切分（保证语义结构）
    2. 再进行 token / 字符切分（控制 chunk 大小）
    3. 添加 metadata
    4. embedding
    5. 写入 ChromaDB
    """
    if persist_directory is None:
        persist_directory = get_vector_store_config()["persist_directory"]

    rag_cfg = get_rag_config()
    if chunk_size is None:
        chunk_size = rag_cfg.get("chunk_size", 512)
    if chunk_overlap is None:
        chunk_overlap = rag_cfg.get("chunk_overlap", 50)

    # Markdown header splitter
    headers = [
        ("#", "h1"),
    ]

    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers)

    # 再次细分
    recursive_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    all_chunks = []
    all_metas = []

    for i, text in enumerate(texts):

        meta = metadatas[i] if metadatas else {}

        # 1️⃣ Markdown 结构切分
        md_docs = md_splitter.split_text(text)

        for doc in md_docs:

            header_meta = doc.metadata
            section_text = doc.page_content

            # 2️⃣ 再次 token 切分
            sub_chunks = recursive_splitter.split_text(section_text)

            for ci, chunk in enumerate(sub_chunks):

                all_chunks.append(chunk)

                all_metas.append({
                    **meta,
                    **header_meta,
                    "chunk_index": ci
                })

    embeddings = get_embedding_model()

    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_directory,
    )

    ids = [
        hashlib.md5((meta.get("source_file", "") + chunk).encode("utf-8")).hexdigest()
        for chunk, meta in zip(all_chunks, all_metas)
    ]

    vectorstore.add_texts(
        texts=all_chunks,
        metadatas=all_metas,
        ids=ids
    )

    return vectorstore
