"""test_match_scorer.py — 匹配度计算工具测试"""

from tools.match_scorer import compute_match_score


class TestMatchScorer:
    """测试 compute_match_score 函数。"""

    def test_full_match(self):
        result = compute_match_score(
            jd_skills=["Python", "LangChain", "RAG"],
            personal_skills=["python", "langchain", "rag", "pytorch"],
        )
        assert result["score"] == 1.0
        assert len(result["matched"]) == 3
        assert result["missing"] == []

    def test_partial_match(self):
        result = compute_match_score(
            jd_skills=["Python", "Java", "Go", "Rust"],
            personal_skills=["Python", "Java"],
        )
        assert result["score"] == 0.5
        assert "python" in result["matched"]
        assert "go" in result["missing"]

    def test_no_match(self):
        result = compute_match_score(
            jd_skills=["Java", "Kotlin"],
            personal_skills=["Python", "Rust"],
        )
        assert result["score"] == 0.0
        assert result["matched"] == []
        assert len(result["missing"]) == 2

    def test_empty_jd(self):
        result = compute_match_score(
            jd_skills=[],
            personal_skills=["Python"],
        )
        assert result["score"] == 0.0

    def test_case_insensitive(self):
        result = compute_match_score(
            jd_skills=["PYTHON", "langChain"],
            personal_skills=["python", "LangChain"],
        )
        assert result["score"] == 1.0
