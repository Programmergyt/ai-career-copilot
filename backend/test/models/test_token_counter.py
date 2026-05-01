"""Token counter unit tests."""

from __future__ import annotations

from models.token_counter import TokenCounter, extract_usage_tokens


def test_heuristic_counter_counts_cjk_and_words():
    counter = TokenCounter(provider="deepseek", model="deepseek-chat", method="heuristic")

    assert counter.count_text("Python RAG 项目经验") >= 5


def test_extract_usage_from_response_metadata():
    class Response:
        response_metadata = {
            "token_usage": {
                "prompt_tokens": 12,
                "completion_tokens": 8,
                "total_tokens": 20,
            }
        }

    usage = extract_usage_tokens(Response())

    assert usage["prompt_tokens"] == 12
    assert usage["completion_tokens"] == 8
    assert usage["total_tokens"] == 20
    assert usage["source"] == "response_metadata"
