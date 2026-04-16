"""LLM 统一封装：基于 config.yaml 的 provider 动态创建 LangChain Chat Model。"""

import json
import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config_loader import get_config, get_llm_config, _resolve_api_key


_llm_instance: Any | None = None


def _normalize_provider(provider: str) -> str:
    return (provider or "openai").strip().lower()


def _create_openai_compatible_llm(cfg: dict) -> Any:
    kwargs: dict[str, Any] = {
        "model": cfg["model"],
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
    }
    if cfg.get("api_key"):
        kwargs["openai_api_key"] = cfg["api_key"]
    if cfg.get("api_base"):
        kwargs["openai_api_base"] = cfg["api_base"]
    if cfg.get("timeout") is not None:
        kwargs["request_timeout"] = cfg["timeout"]

    model_kwargs = cfg.get("model_kwargs") or {}
    if model_kwargs:
        kwargs["model_kwargs"] = model_kwargs

    return ChatOpenAI(**kwargs)


def _create_azure_openai_llm(cfg: dict) -> Any:
    from langchain_openai import AzureChatOpenAI

    kwargs: dict[str, Any] = {
        "azure_deployment": cfg.get("deployment") or cfg["model"],
        "api_version": cfg.get("api_version") or "2024-02-15-preview",
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
    }
    if cfg.get("api_base"):
        kwargs["azure_endpoint"] = cfg["api_base"]
    if cfg.get("api_key"):
        kwargs["api_key"] = cfg["api_key"]

    model_kwargs = cfg.get("model_kwargs") or {}
    if model_kwargs:
        kwargs["model_kwargs"] = model_kwargs

    return AzureChatOpenAI(**kwargs)


def _create_anthropic_llm(cfg: dict) -> Any:
    from langchain_anthropic import ChatAnthropic

    kwargs: dict[str, Any] = {
        "model": cfg["model"],
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
    }
    if cfg.get("api_key"):
        kwargs["anthropic_api_key"] = cfg["api_key"]

    return ChatAnthropic(**kwargs)


def _create_ollama_llm(cfg: dict) -> Any:
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        from langchain_community.chat_models import ChatOllama

    kwargs: dict[str, Any] = {
        "model": cfg["model"],
        "temperature": cfg["temperature"],
    }
    if cfg.get("api_base"):
        kwargs["base_url"] = cfg["api_base"]

    return ChatOllama(**kwargs)


def setup_langsmith() -> str | None:
    """从 config.yaml 读取配置并设置 LangSmith 环境变量。"""
    cfg = get_config().get("langsmith", {})
    if not cfg.get("tracing_v2"):
        return None

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    project = cfg.get("project", "ai-career-copilot")
    os.environ["LANGCHAIN_PROJECT"] = project

    api_key_env = cfg.get("api_key_env", "LANGCHAIN_API_KEY")
    api_key = _resolve_api_key(api_key_env)
    if api_key:
        os.environ["LANGCHAIN_API_KEY"] = api_key

    endpoint = cfg.get("endpoint", "https://api.smith.langchain.com")
    os.environ["LANGCHAIN_ENDPOINT"] = endpoint

    return f"https://smith.langchain.com/o/default/projects?filter=name%3D{project}"


def get_llm() -> Any:
    """获取或创建共享的 LLM 实例。"""
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    cfg = get_llm_config()
    provider = _normalize_provider(cfg.get("provider", "openai"))

    if provider in {"openai", "deepseek", "qwen", "openai_compatible"}:
        _llm_instance = _create_openai_compatible_llm(cfg)
    elif provider in {"azure_openai", "azure"}:
        _llm_instance = _create_azure_openai_llm(cfg)
    elif provider in {"anthropic", "claude"}:
        _llm_instance = _create_anthropic_llm(cfg)
    elif provider in {"ollama", "local"}:
        _llm_instance = _create_ollama_llm(cfg)
    else:
        raise ValueError(
            "Unsupported llm.provider='{}'. Supported providers: openai, deepseek, "
            "qwen, openai_compatible, azure_openai, anthropic, ollama".format(provider)
        )

    return _llm_instance


def call_llm(system: str, user: str) -> str:
    """调用 LLM，返回文本结果。"""
    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=user),
    ])
    content = response.content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text", "")))
            else:
                parts.append(str(part))
        return "".join(parts).strip()
    return str(content).strip()


def parse_json_response(text: str):
    """从 LLM 回复中解析 JSON，兼容 ```json 包裹。"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)
