"""test_file_parser.py — 文件解析工具测试"""

import pytest
from tools.file_parser import parse_file, parse_directory


class TestParseFile:
    """测试 parse_file 函数。"""

    def test_parse_md(self, sample_md_file):
        text = parse_file(sample_md_file)
        assert "RAG 故障诊断系统" in text
        assert "LangChain" in text

    def test_parse_txt(self, sample_txt_file):
        text = parse_file(sample_txt_file)
        assert "Python" in text
        assert "机器学习" in text

    def test_parse_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            parse_file("/nonexistent/file.md")

    def test_parse_unsupported_format(self, tmp_path):
        f = tmp_path / "test.xyz"
        f.write_text("hello")
        with pytest.raises(ValueError, match="不支持的文件格式"):
            parse_file(str(f))


class TestParseDirectory:
    """测试 parse_directory 函数。"""

    def test_parse_dir(self, tmp_path):
        (tmp_path / "a.md").write_text("文档A内容", encoding="utf-8")
        (tmp_path / "b.txt").write_text("文档B内容", encoding="utf-8")
        (tmp_path / "c.xyz").write_text("不支持格式")

        result = parse_directory(str(tmp_path))
        assert len(result) == 2
        contents = list(result.values())
        assert any("文档A" in c for c in contents)
        assert any("文档B" in c for c in contents)

    def test_parse_empty_dir(self, tmp_path):
        result = parse_directory(str(tmp_path))
        assert result == {}
