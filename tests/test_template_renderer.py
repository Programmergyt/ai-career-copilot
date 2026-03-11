"""test_template_renderer.py — 模板渲染工具测试"""

from tools.template_renderer import render_markdown, save_output


class TestRenderMarkdown:
    """测试 Markdown 模板渲染。"""

    def test_render_basic(self, tmp_path):
        tpl = tmp_path / "tpl.md"
        tpl.write_text("# $name\n\n$skills", encoding="utf-8")

        result = render_markdown(str(tpl), {"name": "张三", "skills": "Python, Java"})
        assert "张三" in result
        assert "Python, Java" in result

    def test_render_missing_var(self, tmp_path):
        tpl = tmp_path / "tpl.md"
        tpl.write_text("# $name\n\n$missing_key", encoding="utf-8")

        result = render_markdown(str(tpl), {"name": "李四"})
        assert "李四" in result
        assert "$missing_key" in result  # safe_substitute 保留未匹配变量


class TestSaveOutput:
    """测试文件保存。"""

    def test_save(self, tmp_path):
        out = str(tmp_path / "sub" / "out.md")
        result_path = save_output("hello world", out)
        assert "out.md" in result_path
        with open(result_path, encoding="utf-8") as f:
            assert f.read() == "hello world"
