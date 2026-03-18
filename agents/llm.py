"""共享 LangChain LLM 工具 — 提供统一的 LLM 调用接口并集成 LangSmith 追踪"""

import json
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from config_loader import get_llm_config, get_config, _resolve_api_key


_llm_instance: ChatOpenAI | None = None


def setup_langsmith() -> str | None:
    """从 config.yaml 读取配置并设置 LangSmith 环境变量。

    Returns:
        LangSmith 项目面板 URL（如果启用），否则 None
    """
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


def get_llm() -> ChatOpenAI:
    """获取或创建共享的 ChatOpenAI 实例。"""
    global _llm_instance
    if _llm_instance is None:
        cfg = get_llm_config()
        _llm_instance = ChatOpenAI(
            model=cfg["model"],
            openai_api_key=cfg["api_key"],
            openai_api_base=cfg["api_base"],
            temperature=cfg["temperature"],
            max_tokens=cfg["max_tokens"],
        )
    return _llm_instance


def call_llm(system: str, user: str) -> str:
    """调用 LLM，返回回复内容字符串。自动通过 LangSmith 追踪。"""
    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=user),
    ])
    return response.content.strip()


def parse_json_response(text: str):
    """从 LLM 回复中解析 JSON，容忍 ```json 包裹。"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)
