"""LaTeX 编译工具 — 尝试编译 .tex 为 .pdf，失败则跳过"""

import subprocess
import shutil
from pathlib import Path


def compile_latex(tex_path: str, output_dir: str | None = None) -> str | None:
    """编译 LaTeX 文件为 PDF。

    Returns:
        PDF 文件路径（成功），None（失败或 latexmk 不可用）。
    """
    if not shutil.which("latexmk"):
        return None

    tex = Path(tex_path)
    if not tex.exists():
        return None

    if output_dir is None:
        output_dir = str(tex.parent)

    try:
        subprocess.run(
            [
                "latexmk",
                "-xelatex",
                "-interaction=nonstopmode",
                f"-output-directory={output_dir}",
                str(tex),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
        pdf_path = Path(output_dir) / tex.with_suffix(".pdf").name
        if pdf_path.exists():
            return str(pdf_path)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    return None
