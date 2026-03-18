"""全局配置加载器 — 读取 config.yaml 并提供统一的配置访问接口

用法:
    from config_loader import get_llm_config, get_embedding_config, ...
    cfg = get_llm_config()   # {"model": ..., "api_base": ..., "api_key": ..., ...}
"""

import os
from pathlib import Path

import yaml
from dotenv import dotenv_values

_config: dict | None = None
_dotenv: dict | None = None


def _get_dotenv() -> dict:
    """加载 .env 文件内容（缓存）。优先从项目根目录读取。"""
    global _dotenv
    if _dotenv is None:
        env_path = Path(__file__).parent / ".env"
        _dotenv = dotenv_values(env_path) if env_path.exists() else {}
    return _dotenv


def _resolve_api_key(env_var_name: str) -> str:
    """解析 API Key：优先 .env 文件，其次系统环境变量。"""
    dotenv = _get_dotenv()
    return dotenv.get(env_var_name) or os.environ.get(env_var_name, "")


def load_config(config_path: str | None = None) -> dict:
    """加载配置文件并缓存。"""
    global _config
    if config_path is None:
        config_path = str(Path(__file__).parent / "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f)
    return _config


def get_config() -> dict:
    """获取已加载的全局配置，未加载时自动从默认路径加载。"""
    if _config is None:
        load_config()
    return _config


# ------------------------------------------------------------------
# 各模块便捷配置访问
# ------------------------------------------------------------------

def get_llm_config() -> dict:
    """返回 LLM 配置（model, api_base, api_key, temperature, max_tokens）。"""
    cfg = get_config()["llm"]
    return {
        "model": cfg["model"],
        "api_base": cfg["api_base"],
        "api_key": _resolve_api_key(cfg["api_key_env"]),
        "temperature": cfg.get("temperature", 0.3),
        "max_tokens": cfg.get("max_tokens", 4096),
    }


def get_embedding_config() -> dict:
    """返回 Embedding 模型配置（model, api_key）。"""
    cfg = get_config()["embedding"]
    return {
        "model": cfg["model"],
        "api_key": _resolve_api_key(cfg["api_key_env"]),
    }


def get_rerank_config() -> dict:
    """返回 Rerank 模型配置（model, api_key, top_n）。"""
    cfg = get_config()["rerank"]
    return {
        "model": cfg["model"],
        "api_key": _resolve_api_key(cfg["api_key_env"]),
        "top_n": cfg.get("top_n", 5),
    }


def get_rag_config() -> dict:
    """返回 RAG 参数（chunk_size, chunk_overlap, search_top_k, rerank_top_n）。"""
    return get_config()["rag"]


def get_vector_store_config() -> dict:
    """返回向量数据库配置（persist_directory）。"""
    return get_config()["vector_store"]


def get_template_config() -> dict:
    """返回模板路径配置（default_md, default_tex）。"""
    return get_config()["templates"]


def get_output_config() -> dict:
    """返回输出目录配置（directory）。"""
    return get_config()["output"]
