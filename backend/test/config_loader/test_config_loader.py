# 示例: 在项目根目录执行 pytest backend/test/config_loader/test_config_loader.py -sv
"""config_loader 模块单元测试。"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from config_loader import (
    load_config,
    get_config,
    get_server_config,
    get_server_host,
    get_llm_config,
    get_embedding_config,
    get_rerank_config,
    get_redis_config,
    get_mysql_config,
    get_fastapi_config,
    get_testing_config,
    should_run_real_llm_integration_tests,
)


@pytest.fixture(autouse=True)
def reset_config_cache():
    """每个测试前重置全局缓存。"""
    import config_loader
    config_loader._config = None
    config_loader._dotenv = None
    yield
    config_loader._config = None
    config_loader._dotenv = None


class TestLoadConfig:

    def test_load_default_config(self):
        cfg = load_config()
        assert isinstance(cfg, dict)
        assert "llm" in cfg
        assert "embedding" in cfg
        assert "redis" in cfg
        assert "mysql" in cfg

    def test_load_config_caches(self):
        cfg1 = load_config()
        cfg2 = get_config()
        assert cfg1 is cfg2

    def test_get_config_auto_loads(self):
        cfg = get_config()
        assert isinstance(cfg, dict)
        assert "server" in cfg


class TestServerConfig:

    def test_server_host_not_empty(self):
        host = get_server_host()
        assert isinstance(host, str)
        assert len(host) > 0

    def test_server_config_structure(self):
        cfg = get_server_config()
        assert "host" in cfg


class TestLLMConfig:

    def test_llm_config_has_required_fields(self):
        cfg = get_llm_config()
        assert "provider" in cfg
        assert "model" in cfg
        assert "api_base" in cfg
        assert "temperature" in cfg
        assert "max_tokens" in cfg

    def test_llm_config_values(self):
        cfg = get_llm_config()
        assert cfg["model"] == "deepseek-chat"
        assert cfg["provider"] == "deepseek"
        assert isinstance(cfg["temperature"], (int, float))
        assert isinstance(cfg["max_tokens"], int)


class TestEmbeddingConfig:

    def test_embedding_config_has_required_fields(self):
        cfg = get_embedding_config()
        assert "provider" in cfg
        assert "model" in cfg
        assert "api_base" in cfg

    def test_embedding_config_values(self):
        cfg = get_embedding_config()
        assert cfg["model"] == "text-embedding-v4"
        assert cfg["provider"] == "dashscope"


class TestRerankConfig:

    def test_rerank_config_has_required_fields(self):
        cfg = get_rerank_config()
        assert "provider" in cfg
        assert "model" in cfg
        assert "top_n" in cfg

    def test_rerank_config_values(self):
        cfg = get_rerank_config()
        assert cfg["model"] == "gte-rerank-v2"
        assert cfg["top_n"] == 5


class TestRedisConfig:

    def test_redis_config_structure(self):
        cfg = get_redis_config()
        assert "host" in cfg
        assert "port" in cfg
        assert "db" in cfg

    def test_redis_config_host_from_server(self):
        """redis 使用 host_from=server 时应复用 server.host。"""
        cfg = get_redis_config()
        server_host = get_server_host()
        assert cfg["host"] == server_host

    def test_redis_config_defaults(self):
        cfg = get_redis_config()
        assert cfg["port"] == 6379
        assert cfg["db"] == 0


class TestMySQLConfig:

    def test_mysql_config_structure(self):
        cfg = get_mysql_config()
        assert "host" in cfg
        assert "port" in cfg
        assert "user" in cfg
        assert "password" in cfg
        assert "database" in cfg
        assert "charset" in cfg

    def test_mysql_config_host_from_server(self):
        """mysql 使用 host_from=server 时应复用 server.host。"""
        cfg = get_mysql_config()
        server_host = get_server_host()
        assert cfg["host"] == server_host

    def test_mysql_config_values(self):
        cfg = get_mysql_config()
        assert cfg["port"] == 3306
        assert cfg["user"] == "root"
        assert cfg["database"] == "ai_career_copilot"
        assert cfg["charset"] == "utf8mb4"


class TestFastAPIConfig:

    def test_fastapi_config_structure(self):
        cfg = get_fastapi_config()
        assert "host" in cfg
        assert "port" in cfg
        assert "debug" in cfg

    def test_fastapi_config_values(self):
        cfg = get_fastapi_config()
        assert cfg["port"] == 8000


class TestTestingConfig:

    def test_testing_config_structure(self):
        cfg = get_testing_config()
        assert "integration" in cfg
        assert "run_real_llm_tests" in cfg["integration"]

