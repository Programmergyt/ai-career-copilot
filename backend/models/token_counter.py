"""Provider-aware token counting helpers for LLM calls and context budgets."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from config_loader import get_llm_config


_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\sA-Za-z0-9_\u4e00-\u9fff]")


@dataclass(frozen=True)
class TokenUsageEstimate:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class TokenCounter:
    """Counts tokens with provider-specific rules and safe fallbacks."""

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        method: str = "auto",
        chars_per_token: float | None = None,
        message_overhead_tokens: int = 4,
    ) -> None:
        self.provider = _normalize_provider(provider)
        self.model = model
        self.method = method or "auto"
        self.chars_per_token = chars_per_token or _default_chars_per_token(self.provider)
        self.message_overhead_tokens = message_overhead_tokens
        self._encoding = self._load_tiktoken_encoding()

    def count_text(self, text: Any) -> int:
        if text is None:
            return 0
        value = str(text)
        if not value:
            return 0
        if self._encoding is not None:
            try:
                return len(self._encoding.encode(value))
            except Exception:
                pass
        if self.provider in {"anthropic", "claude"}:
            return _heuristic_count(value, chars_per_token=self.chars_per_token, cjk_weight=1.05)
        if self.provider in {"ollama", "local"}:
            return _heuristic_count(value, chars_per_token=self.chars_per_token, cjk_weight=1.0)
        return _heuristic_count(value, chars_per_token=self.chars_per_token, cjk_weight=1.0)

    def count_messages(self, messages: list[Any]) -> int:
        total = 0
        for message in messages:
            content = getattr(message, "content", None)
            if content is None and isinstance(message, dict):
                content = message.get("content")
            total += self.message_overhead_tokens + self.count_text(_content_to_text(content))
        return total + 2

    def truncate_text(self, text: str, max_tokens: int, *, from_start: bool = False) -> tuple[str, int]:
        current_tokens = self.count_text(text)
        if current_tokens <= max_tokens:
            return text, 0
        if max_tokens <= 0:
            return "", current_tokens

        ratio = max_tokens / max(current_tokens, 1)
        keep_chars = max(1, int(len(text) * ratio * 0.95))
        trimmed = text[-keep_chars:] if from_start else text[:keep_chars]

        while self.count_text(trimmed) > max_tokens and len(trimmed) > 1:
            keep_chars = max(1, int(len(trimmed) * 0.9))
            trimmed = trimmed[-keep_chars:] if from_start else trimmed[:keep_chars]

        removed = max(current_tokens - self.count_text(trimmed), 0)
        return trimmed.rstrip(), removed

    def _load_tiktoken_encoding(self) -> Any | None:
        if self.method == "heuristic":
            return None
        if self.provider not in {"openai", "azure_openai", "azure", "deepseek", "qwen", "openai_compatible"}:
            return None
        try:
            import tiktoken  # type: ignore
        except Exception:
            return None
        try:
            return tiktoken.encoding_for_model(self.model)
        except Exception:
            try:
                return tiktoken.get_encoding("cl100k_base")
            except Exception:
                return None


def get_token_counter() -> TokenCounter:
    cfg = get_llm_config()
    token_cfg = cfg.get("token_counter") or {}
    provider = _normalize_provider(cfg.get("provider", "openai"))
    overrides = token_cfg.get("provider_overrides") or {}
    provider_cfg = overrides.get(provider, {})
    return TokenCounter(
        provider=provider,
        model=cfg.get("model", ""),
        method=provider_cfg.get("method", token_cfg.get("method", "auto")),
        chars_per_token=provider_cfg.get("chars_per_token", token_cfg.get("chars_per_token")),
        message_overhead_tokens=int(provider_cfg.get(
            "message_overhead_tokens",
            token_cfg.get("message_overhead_tokens", 4),
        )),
    )


def get_context_window_tokens(default: int = 128 * 1024) -> int:
    cfg = get_llm_config()
    return int(cfg.get("context_window_tokens") or default)


def estimate_payload_tokens(payload: Any) -> int:
    counter = get_token_counter()
    if isinstance(payload, list):
        return counter.count_messages(payload)
    return counter.count_text(payload)


def extract_usage_tokens(response: Any) -> dict[str, int | str]:
    """Extract real provider usage from common LangChain response shapes."""
    for attr in ("usage_metadata", "response_metadata", "llm_output"):
        data = getattr(response, attr, None)
        usage = _extract_usage_from_mapping(data)
        if usage:
            usage["source"] = attr
            return usage
    if isinstance(response, dict):
        usage = _extract_usage_from_mapping(response)
        if usage:
            usage["source"] = "dict"
            return usage
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "source": "estimate"}


def _extract_usage_from_mapping(data: Any) -> dict[str, int] | None:
    if not isinstance(data, dict):
        return None
    candidates = [
        data,
        data.get("token_usage"),
        data.get("usage"),
        data.get("usage_metadata"),
    ]
    for item in candidates:
        if not isinstance(item, dict):
            continue
        prompt = _first_int(item, "prompt_tokens", "input_tokens")
        completion = _first_int(item, "completion_tokens", "output_tokens")
        total = _first_int(item, "total_tokens")
        if total == 0 and (prompt or completion):
            total = prompt + completion
        if prompt or completion or total:
            return {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": total,
            }
    return None


def _first_int(data: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = data.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return 0


def _heuristic_count(text: str, *, chars_per_token: float, cjk_weight: float) -> int:
    if not text:
        return 0
    cjk_count = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    non_cjk = len(text) - cjk_count
    lexical = len(_TOKEN_RE.findall(text))
    char_based = math.ceil((non_cjk / max(chars_per_token, 1.0)) + (cjk_count * cjk_weight))
    return max(1, max(lexical, char_based))


def _default_chars_per_token(provider: str) -> float:
    if provider in {"anthropic", "claude"}:
        return 3.8
    if provider in {"ollama", "local"}:
        return 3.6
    return 3.5


def _normalize_provider(provider: str) -> str:
    return (provider or "openai").strip().lower()


def _content_to_text(content: Any) -> str:
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return "" if content is None else str(content)
