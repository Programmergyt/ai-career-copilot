"""AI Career Copilot — CLI 入口

Usage:
    python main.py --jd <jd_file_or_text> [--docs <file1> <file2> ...]
"""

import argparse
import sys
from pathlib import Path

from workflow.graph import run_pipeline
from tools.file_parser import parse_file
from memory.long_term_memory import init_db


def main():
    parser = argparse.ArgumentParser(
        description="AI Career Copilot — 基于多 Agent 协作的求职辅助系统 (MVP)",
    )
    parser.add_argument(
        "--jd",
        required=True,
        help="JD 内容：文件路径（pdf/docx/md/txt）或直接文本",
    )
    parser.add_argument(
        "--docs",
        nargs="*",
        default=[],
        help="个人材料文件路径列表（pdf/docx/md/txt）",
    )
    parser.add_argument(
        "--template",
        default="./templates/default.md",
        help="简历模板路径（默认 ./templates/default.md）",
    )

    args = parser.parse_args()

    # 初始化长期记忆数据库
    init_db()

    # 解析 JD：如果是文件路径则读取文件内容，否则视为直接文本
    jd_path = Path(args.jd)
    if jd_path.exists() and jd_path.is_file():
        print(f"📄 读取 JD 文件: {jd_path}")
        jd_text = parse_file(str(jd_path))
    else:
        jd_text = args.jd

    if not jd_text.strip():
        print("❌ JD 内容为空，请提供有效的 JD。")
        sys.exit(1)

    # 验证个人材料文件
    valid_docs = []
    for doc in args.docs:
        p = Path(doc)
        if p.exists():
            valid_docs.append(str(p))
        else:
            print(f"⚠️  文件不存在，跳过: {doc}")

    print(f"\n{'='*60}")
    print("🚀 AI Career Copilot — MVP Pipeline")
    print(f"{'='*60}")
    print(f"JD 长度: {len(jd_text)} 字符")
    print(f"个人材料: {len(valid_docs)} 份文件")
    print(f"{'='*60}\n")

    # 运行 Pipeline
    try:
        final_state = run_pipeline(
            jd_text=jd_text,
            personal_docs=valid_docs,
            template_path=args.template,
        )
    except Exception as e:
        print(f"\n❌ Pipeline 执行失败: {e}")
        sys.exit(1)

    # 输出结果
    print(f"\n{'='*60}")
    print("📊 执行日志:")
    print(f"{'='*60}")
    for log in final_state.get("analysis_log", []):
        print(log)

    resume_file = final_state.get("resume_file")
    if resume_file:
        print(f"\n✅ 简历已生成: {resume_file}")
    else:
        print("\n⚠️  简历未能成功生成，请检查日志。")

    print(f"\n📁 所有输出文件在 ./output/ 目录下")


if __name__ == "__main__":
    main()
