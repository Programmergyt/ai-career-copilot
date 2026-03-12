"""文档入库 — 将文本分块后写入 ChromaDB 向量数据库"""

import os
import uuid
from langchain_text_splitters  import RecursiveCharacterTextSplitter,MarkdownHeaderTextSplitter
from langchain_community.vectorstores import Chroma

from rag.embeddings import get_embedding_model


def build_index(
    texts: list[str],
    metadatas: list[dict] | None = None,
    collection_name: str = "personal_knowledge",
    persist_directory: str | None = None,
    chunk_size: int = 1024,
    chunk_overlap: int = 100,
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
        persist_directory = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")

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

    ids = [str(uuid.uuid4()) for _ in all_chunks]

    vectorstore.add_texts(
        texts=all_chunks,
        metadatas=all_metas,
        ids=ids
    )

    return vectorstore
