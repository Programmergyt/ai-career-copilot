# 示例: 在项目根目录执行 pytest backend/test/connectivity/test_connectivity.py -sv

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
    """验证项目配置的真实 LangChain LLM 连通性。

    LangSmith trace 名称：Test-Connectivity: LangChain LLM

    与 workflow/agent 测试不同，这里没有 monkeypatch get_llm，因此会真实创建模型实例，
    并尝试访问 config.yaml 所配置的 LLM 服务。这个测试适合定位：
    1. API Key、Base URL、模型名是否正确；
    2. 网络与鉴权是否可用；
    3. LangSmith 中单次底层模型调用的原始 trace。
    """
    from models.llm import get_llm

    llm = get_llm()
    # 使用最小 prompt 做一次直接调用，避免把业务 prompt 与连通性诊断混在一起。
    # 如果这里失败，问题就在模型访问层，而不是 workflow 编排层。
    response = llm.invoke("Reply only with: pong", config={"run_name": "Test-Connectivity: LangChain LLM"})
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
