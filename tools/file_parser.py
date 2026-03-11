"""文件解析工具 — 支持 pdf / docx / md / txt 文件解析为纯文本"""

import os
from pathlib import Path

# pdf 解析使用 pdfplumber（轻量）
# docx 解析使用 python-docx


def parse_file(file_path: str) -> str:
    """解析单个文件，返回纯文本内容。

    支持格式: .pdf, .docx, .md, .txt, .tex
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _parse_pdf(path)
    elif suffix == ".docx":
        return _parse_docx(path)
    elif suffix in (".md", ".txt", ".tex"):
        return _parse_text(path)
    else:
        raise ValueError(f"不支持的文件格式: {suffix}")


def parse_directory(dir_path: str, extensions: list[str] | None = None) -> dict[str, str]:
    """解析目录下所有支持的文件，返回 {文件路径: 文本内容}。"""
    if extensions is None:
        extensions = [".pdf", ".docx", ".md", ".txt", ".tex"]

    results = {}
    for root, _dirs, files in os.walk(dir_path):
        for fname in files:
            fpath = os.path.join(root, fname)
            if Path(fpath).suffix.lower() in extensions:
                try:
                    results[fpath] = parse_file(fpath)
                except Exception as e:
                    results[fpath] = f"[解析失败] {e}"
    return results


# ---- 内部解析函数 ----

def _parse_pdf(path: Path) -> str:
    import pdfplumber

    texts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                texts.append(text)
    return "\n\n".join(texts)


def _parse_docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _parse_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")
