# 示例: 在项目根目录执行 pytest backend/test/tools/test_file_parser.py -sv
"""file_parser 模块单元测试 — 利用 fixtures 中的 Markdown 测试数据。"""

import pytest
from pathlib import Path

from tools.file_parser import parse_file, parse_content, parse_content_bytes, supported_upload_suffixes

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestParseMarkdownFiles:
    """使用 fixtures 目录下的 .md 文件测试解析功能。"""

    def test_parse_jd_file(self):
        jd_path = FIXTURES_DIR / "jds" / "通用AIGC实习JD.md"
        text = parse_file(jd_path)
        assert isinstance(text, str)
        assert len(text) > 0
        assert "NovaWorks" in text
        assert "Generative AI" in text or "GenAI" in text

    def test_parse_profile_file(self):
        profile_path = FIXTURES_DIR / "profiles" / "虚拟候选人信息.md"
        text = parse_file(profile_path)
        assert isinstance(text, str)
        assert len(text) > 0
        assert "林知遥" in text
        assert "星海理工大学" in text

    def test_parse_internship_file(self):
        intern_path = FIXTURES_DIR / "internships" / "远望工业智能实习——RAG诊断平台.md"
        text = parse_file(intern_path)
        assert isinstance(text, str)
        assert len(text) > 0
        assert "RAG" in text
        assert "向量" in text

    def test_parse_project_file(self):
        project_path = FIXTURES_DIR / "projects" / "求职Agent_README.md"
        text = parse_file(project_path)
        assert isinstance(text, str)
        assert len(text) > 0
        assert "LangGraph" in text
        assert "Agent" in text


class TestParseContent:
    """测试 parse_content 直接解析字符串。"""

    def test_parse_plain_text(self):
        text = parse_content("Hello World", filename="test.txt")
        assert text == "Hello World"

    def test_parse_without_filename(self):
        text = parse_content("测试内容")
        assert text == "测试内容"

    def test_parse_md_content(self):
        text = parse_content("# Title\n\nSome content", filename="readme.md")
        assert "Title" in text

    def test_parse_content_bytes_plain_text(self):
        text = parse_content_bytes("测试内容".encode("utf-8"), filename="note.txt")
        assert text == "测试内容"


class TestParseUnsupportedType:

    def test_parse_unknown_extension_as_text(self, tmp_path):
        """未知扩展名应拒绝解析。"""
        f = tmp_path / "data.xyz"
        f.write_text("some content", encoding="utf-8")
        with pytest.raises(ValueError):
            parse_file(f)

    def test_supported_upload_suffixes(self):
        assert supported_upload_suffixes() == {".pdf", ".docx", ".txt", ".md"}
