"""模板渲染工具 — 将结构化内容填充到 Markdown 模板"""

from pathlib import Path
from string import Template


def render_markdown(template_path: str, context: dict) -> str:
    """读取 Markdown 模板并用 context 字典填充。

    模板使用 Python string.Template 语法：$variable 或 ${variable}。
    """
    tpl_text = Path(template_path).read_text(encoding="utf-8")
    template = Template(tpl_text)
    return template.safe_substitute(context)


def save_output(content: str, output_path: str) -> str:
    """将内容保存到文件，返回绝对路径。"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path.resolve())
