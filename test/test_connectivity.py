# python -m pytest -sv test/test_connectivity.py

import pytest

from config_loader import get_server_host, get_mysql_config, get_redis_config


def test_mysql_connection() -> None:
    pymysql = pytest.importorskip("pymysql")
    cfg = get_mysql_config()

    connection = pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset=cfg["charset"],
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION();")
            result = cursor.fetchone()
    finally:
        connection.close()

    assert result is not None
    assert result[0]


def test_redis_connection() -> None:
    redis = pytest.importorskip("redis")
    cfg = get_redis_config()

    client = redis.Redis(
        host=cfg["host"],
        port=cfg["port"],
        db=cfg["db"],
        password=cfg.get("password") or None,
        decode_responses=True,
    )
    client.set("test_key", "Hello Redis!")
    value = client.get("test_key")

    assert value == "Hello Redis!"


def test_langchain_llm_connection() -> None:
    from models.llm import get_llm

    llm = get_llm()
    response = llm.invoke("Reply only with: pong")
    content = getattr(response, "content", response)

    assert content is not None
    assert "pong" in str(content).lower()


def test_langchain_embedding_connection() -> None:
    from models.embedding import get_embedding_model

    embedding_model = get_embedding_model()
    vector = embedding_model.embed_query("langchain embedding connection test")

    assert isinstance(vector, list)
    assert len(vector) > 0
    assert all(isinstance(item, float) for item in vector[:5])


def test_langchain_rerank_connection() -> None:
    from models.rerank import rerank_texts

    documents = [
        "I have strong Python and LangChain experience.",
        "I mainly focus on frontend CSS animation.",
        "Built RAG systems with vector databases and reranking.",
    ]
    results = rerank_texts(
        documents=documents,
        query="Find candidate profile related to Python and RAG",
        top_n=min(2, len(documents)),
    )

    assert isinstance(results, list)
    assert len(results) > 0
    assert "index" in results[0]
    assert "relevance_score" in results[0]
